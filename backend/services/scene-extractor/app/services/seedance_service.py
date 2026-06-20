import logging
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
import json
import hashlib

import httpx
from PIL import Image
import io
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.media_asset import MediaAsset, MediaType

logger = logging.getLogger(__name__)


class SeedanceService:
    """Seedance AI服务集成，用于图像生成"""

    def __init__(self):
        self.api_url = settings.SEEDANCE_API_URL
        self.api_key = settings.SEEDANCE_API_KEY
        self.timeout = settings.SEEDANCE_TIMEOUT
        self._initialized = False
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """初始化Seedance服务"""
        if self._initialized:
            return

        try:
            logger.info("初始化Seedance服务...")

            # 验证API密钥
            if not self.api_key:
                logger.warning("SEEDANCE_API_KEY未配置，服务将无法使用")

            # 创建HTTP客户端
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )

            self._initialized = True
            logger.info("Seedance服务初始化完成")

        except Exception as e:
            logger.error(f"Seedance服务初始化失败: {e}")
            raise

    async def close(self):
        """关闭Seedance服务"""
        if self._client:
            await self._client.aclose()
            self._initialized = False
            logger.info("Seedance服务已关闭")

    async def _store_to_ceph(
        self,
        source_url: str,
        media_type: str,
        content_type: str,
        related_entity_type: str,
        related_entity_id: str,
        user_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        将 AI 生成的媒体从源 URL 下载并上传到 Ceph，同时记录到数据库

        返回: (ceph_url, object_key, file_size)
        """
        from app.services.storage_service import get_storage_service

        try:
            storage = await get_storage_service()

            object_key, presigned_url, file_size = await storage.upload_from_url(
                url=source_url,
                media_type=media_type,
                content_type=content_type,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )

            if object_key is None:
                logger.error(f"上传到Ceph失败: {source_url[:80]}...")
                return source_url, None, None

            ceph_url = presigned_url or storage.get_object_url(object_key)

            if db_session is not None:
                try:
                    media_asset = MediaAsset(
                        object_key=object_key,
                        bucket=settings.STORAGE_BUCKET,
                        media_type=MediaType.IMAGE if media_type == "image" else MediaType.VIDEO,
                        content_type=content_type,
                        file_size=file_size or 0,
                        original_url=source_url,
                        ceph_url=ceph_url,
                        source_service="scene-extractor",
                        related_entity_type=related_entity_type,
                        related_entity_id=related_entity_id,
                        user_id=user_id,
                    )
                    db_session.add(media_asset)
                    await db_session.commit()
                    logger.info(f"媒体资产已记录到数据库: id={media_asset.id}, key={object_key}")
                except Exception as db_err:
                    logger.error(f"记录媒体资产到数据库失败: {db_err}")
                    await db_session.rollback()

            return ceph_url, object_key, file_size

        except Exception as e:
            logger.error(f"存储到Ceph失败: {e}")
            return source_url, None, None

    def _generate_seed(self, prompt: str, custom_seed: Optional[int] = None) -> int:
        """生成种子，支持自定义种子"""
        if custom_seed is not None:
            return custom_seed
        # 使用提示词的哈希值作为种子，确保相同提示生成相同结果
        seed_hash = hashlib.md5(prompt.encode()).hexdigest()
        return int(seed_hash[:8], 16) % (2**31)

    async def _submit_image_generation_job(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1920,
        height: int = 1080,
        seed: Optional[int] = None,
        steps: int = 30,
        scale: float = 7.5,
        sampler: str = "DPM++ 2M Karras"
    ) -> Tuple[Optional[str], Optional[int]]:
        """
        提交图像生成任务到Seedance

        返回: (job_id, seed)
        """
        if not self.api_key:
            logger.error("API密钥未配置")
            return None, None

        final_seed = self._generate_seed(prompt, seed)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": final_seed,
            "steps": steps,
            "scale": scale,
            "sampler": sampler,
            "model": "realistic-vision",
        }

        try:
            logger.info(f"提交图像生成任务: prompt={prompt[:50]}...")

            response = await self._client.post(
                f"{self.api_url}/v1/images/generate",
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            job_id = result.get("job_id") or result.get("id")

            logger.info(f"图像生成任务已提交: job_id={job_id}")
            return job_id, final_seed

        except httpx.HTTPStatusError as e:
            logger.error(f"图像生成任务提交失败: {e.response.text}")
            return None, None
        except Exception as e:
            logger.error(f"图像生成任务提交异常: {e}")
            return None, None

    async def _poll_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        轮询任务状态

        返回: 任务结果或None
        """
        max_polls = 60
        poll_interval = 5

        for i in range(max_polls):
            try:
                response = await self._client.get(
                    f"{self.api_url}/v1/jobs/{job_id}"
                )
                response.raise_for_status()

                result = response.json()
                status = result.get("status")

                logger.info(f"轮询任务状态 ({job_id}): {status} ({i+1}/{max_polls})")

                if status == "completed":
                    return result
                elif status == "failed":
                    logger.error(f"任务失败: {result}")
                    return None
                elif status in ("pending", "processing"):
                    await asyncio.sleep(poll_interval)
                else:
                    logger.warning(f"未知状态: {status}")
                    return None

            except Exception as e:
                logger.error(f"轮询任务状态异常: {e}")
                return None

        logger.error(f"任务轮询超时: {job_id}")
        return None

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1920,
        height: int = 1080,
        seed: Optional[int] = None,
        steps: int = 30,
        scale: float = 7.5,
        sampler: str = "DPM++ 2M Karras",
        store_to_ceph: bool = True,
        related_entity_type: str = "scene",
        related_entity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        生成图像（同步方式）

        参数:
            store_to_ceph: 是否存储到 Ceph
            related_entity_type: 关联实体类型
            related_entity_id: 关联实体 ID
            user_id: 用户 ID
            db_session: 数据库会话

        返回: 包含image_url(ceph_url), seed等信息的字典
        """
        if not self._initialized:
            await self.initialize()

        # 提交任务
        job_id, final_seed = await self._submit_image_generation_job(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            scale=scale,
            sampler=sampler
        )

        if not job_id:
            return None

        # 轮询结果
        result = await self._poll_job_status(job_id)

        if result:
            source_image_url = result.get("output", {}).get("image_url") or result.get("image_url")
            image_url = source_image_url
            object_key = None
            file_size = None

            # 存储到 Ceph
            if store_to_ceph and source_image_url:
                entity_id = related_entity_id or job_id
                image_url, object_key, file_size = await self._store_to_ceph(
                    source_url=source_image_url,
                    media_type="image",
                    content_type="image/png",
                    related_entity_type=related_entity_type,
                    related_entity_id=entity_id,
                    user_id=user_id,
                    db_session=db_session,
                )

            return {
                "status": "completed",
                "image_url": image_url,
                "original_url": source_image_url,
                "object_key": object_key,
                "file_size": file_size,
                "seed": final_seed,
                "job_id": job_id,
                "message": "Image generated successfully"
            }
        return None

    async def generate_image_from_scene(
        self,
        scene_description: str,
        style: str = "写实风格",
        width: int = None,
        height: int = None,
        steps: int = None,
    ) -> Optional[Dict[str, Any]]:
        """
        从场景描述生成图像

        参数:
            scene_description: 场景描述
            style: 风格描述
        """
        if width is None:
            width = settings.IMAGE_WIDTH
        if height is None:
            height = settings.IMAGE_HEIGHT
        if steps is None:
            steps = settings.IMAGE_STEPS

        # 构建提示词
        prompt = f"{style}，{scene_description}"
        negative_prompt = "模糊，低质量，变形，水印，文字，多个人物，复杂背景"

        return await self.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            scale=settings.IMAGE_SCALE,
            sampler=settings.IMAGE_SAMPLER
        )


# 全局服务实例
_seedance_service: Optional[SeedanceService] = None


async def get_seedance_service() -> SeedanceService:
    """获取全局Seedance服务实例"""
    global _seedance_service
    if _seedance_service is None:
        _seedance_service = SeedanceService()
        await _seedance_service.initialize()
    return _seedance_service


async def close_seedance_service():
    """关闭全局Seedance服务实例"""
    global _seedance_service
    if _seedance_service:
        await _seedance_service.close()
        _seedance_service = None
