import logging
import time
import asyncio
import uuid
import base64
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
    """Seedance/Seedream AI服务集成（火山引擎 Ark API）"""

    def __init__(self):
        self.api_url = settings.SEEDANCE_API_URL
        self.api_key = settings.SEEDANCE_API_KEY
        self.model = getattr(settings, 'SEEDANCE_MODEL', 'doubao-seedream-4-5-251128')
        self.video_model = getattr(settings, 'SEEDANCE_VIDEO_MODEL', 'doubao-seedance-2-0-260128')
        self.timeout = settings.SEEDANCE_TIMEOUT
        self._initialized = False
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        if self._initialized:
            return
        try:
            logger.info("初始化Seedance服务...")
            if not self.api_key:
                logger.warning("SEEDANCE_API_KEY未配置，服务将无法使用")
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            self._initialized = True
            logger.info(f"Seedance初始化: url={self.api_url}, image_model={self.model}, video_model={self.video_model}")
        except Exception as e:
            logger.error(f"Seedance初始化失败: {e}")
            raise

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._initialized = False

    # ================================================================
    # 存储 (MinIO / Ceph)
    # ================================================================

    async def _store_to_ceph(self, source_url, media_type, content_type,
                             related_entity_type, related_entity_id,
                             user_id=None, db_session=None):
        from app.services.storage_service import get_storage_service
        try:
            storage = await get_storage_service()
            object_key, presigned_url, file_size = await storage.upload_from_url(
                url=source_url, media_type=media_type, content_type=content_type,
                related_entity_type=related_entity_type, related_entity_id=related_entity_id,
            )
            if object_key is None:
                return source_url, None, None
            ceph_url = presigned_url or storage.get_object_url(object_key)
            return ceph_url, object_key, file_size
        except Exception as e:
            logger.warning(f"存储失败，使用原始URL: {e}")
            return source_url, None, None

    def _generate_seed(self, prompt: str, custom_seed: Optional[int] = None) -> int:
        if custom_seed is not None:
            return custom_seed
        seed_hash = hashlib.md5(prompt.encode()).hexdigest()
        return int(seed_hash[:8], 16) % (2**31)

    # ================================================================
    # 图像生成 (Seedream 4.5 via Ark API)
    # ================================================================

    async def _submit_image_generation_job(self, prompt: str, **kwargs):
        if not self.api_key:
            raise ValueError("SEEDANCE_API_KEY 未配置")
        width = kwargs.get("width", 1920)
        height = kwargs.get("height", 1920)
        payload = {"model": self.model, "prompt": prompt, "size": f"{width}x{height}", "n": 1, "response_format": "url"}
        last_body = ""
        for endpoint in [f"{self.api_url}/images/generations", f"{self.api_url}/contents/generations"]:
            try:
                logger.info(f"调用 Ark API: {endpoint}, model={self.model}")
                response = await self._client.post(endpoint, json=payload)
                if response.status_code >= 500:
                    last_body = response.text[:500]
                    continue
                if response.status_code >= 400:
                    last_body = response.text[:800]
                    logger.error(f"Ark API [{response.status_code}]: {last_body}")
                    break
                result = response.json()
                logger.info(f"Ark 响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                image_url = None
                if "data" in result and isinstance(result["data"], list) and len(result["data"]) > 0:
                    image_url = result["data"][0].get("url") or result["data"][0].get("b64_json")
                if not image_url and "url" in result:
                    image_url = result["url"]
                if not image_url and "output" in result:
                    image_url = result["output"].get("image_url") or result["output"].get("url")
                if image_url:
                    logger.info(f"图像生成成功: {image_url[:80]}")
                    return result.get("id") or str(uuid.uuid4()), image_url
                last_body = json.dumps(result, ensure_ascii=False)[:500]
                break
            except httpx.HTTPStatusError as e:
                last_body = e.response.text[:800] if e.response else ""
            except Exception as e:
                last_body = str(e)
        raise RuntimeError(f"图像生成失败: {last_body or 'API无响应'}")

    async def generate_image(self, prompt, negative_prompt="", width=1920, height=1920,
                             seed=None, store_to_ceph=True, related_entity_type="scene",
                             related_entity_id=None, user_id=None, db_session=None, **kwargs):
        if not self._initialized:
            await self.initialize()
        try:
            job_id, source_image_url = await self._submit_image_generation_job(
                prompt=prompt, width=width, height=height, seed=seed, **kwargs)
        except Exception as e:
            logger.error(f"图像生成异常: {e}")
            return None
        if not source_image_url:
            return None
        image_url = source_image_url
        if store_to_ceph and source_image_url:
            entity_id = related_entity_id or (job_id or str(uuid.uuid4()))
            image_url, _, _ = await self._store_to_ceph(
                source_url=source_image_url, media_type="image", content_type="image/png",
                related_entity_type=related_entity_type, related_entity_id=entity_id,
                user_id=user_id, db_session=db_session)
        return {"status": "completed", "image_url": image_url, "original_url": source_image_url,
                "job_id": job_id, "message": "Image generated successfully"}

    async def generate_image_from_scene(self, scene_description, style="写实风格", **kwargs):
        prompt = f"{style}，{scene_description}" if style else scene_description
        return await self.generate_image(prompt=prompt, negative_prompt="模糊，低质量，变形，水印，文字", **kwargs)

    # ================================================================
    # 视频生成 (Seedance 2.0 via Ark API)
    # Ref: https://www.volcengine.com/docs/82379/1520757
    # ================================================================

    @staticmethod
    async def _download_image_bytes(url: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.content
        except Exception as e:
            logger.error(f"下载图片失败: {e}")
        return None

    async def _submit_video_generation_task(self, image_url: str, prompt: str, duration: int = 5) -> Optional[str]:
        """创建 Seedance 2.0 视频生成任务，返回 task_id"""
        if not self.api_key:
            raise ValueError("SEEDANCE_API_KEY 未配置")
        image_bytes = await self._download_image_bytes(image_url)
        if not image_bytes:
            return None
        data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        payload = {
            "model": self.video_model,
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}, "role": "first_frame"},
            ],
            "resolution": "720p", "ratio": "16:9", "duration": duration, "watermark": False,
        }
        url = f"{self.api_url}/contents/generations/tasks"
        logger.info(f"提交视频任务: model={self.video_model}")
        try:
            response = await self._client.post(url, json=payload)
            if response.status_code >= 400:
                logger.error(f"视频任务创建失败 [{response.status_code}]: {response.text[:800]}")
                return None
            result = response.json()
            task_id = result.get("id")
            logger.info(f"视频任务已创建: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"视频任务创建异常: {e}")
            return None

    async def _poll_video_task(self, task_id: str) -> Optional[str]:
        """轮询视频任务直到完成，返回 video_url"""
        url = f"{self.api_url}/contents/generations/tasks/{task_id}"
        for i in range(120):
            try:
                response = await self._client.get(url)
                if response.status_code >= 400:
                    await asyncio.sleep(2)
                    continue
                result = response.json()
                status = result.get("status")
                if status == "succeeded":
                    return result["content"]["video_url"]
                elif status == "failed":
                    logger.error(f"视频任务失败: {json.dumps(result, ensure_ascii=False)[:500]}")
                    return None
                if i % 10 == 0:
                    logger.info(f"视频生成中: {status} ({i+1}/120)")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"视频轮询异常: {e}")
                await asyncio.sleep(2)
        logger.error(f"视频任务超时: {task_id}")
        return None

    async def generate_video(self, image_url: str, prompt: str, duration: float = 5.0,
                             seed=None, store_to_ceph=True, related_entity_type="scene",
                             related_entity_id=None, user_id=None, db_session=None, **kwargs):
        """生成视频 (Seedance 2.0)。创建任务→轮询→存储。"""
        if not self._initialized:
            await self.initialize()
        try:
            task_id = await self._submit_video_generation_task(
                image_url=image_url, prompt=prompt, duration=int(duration))
            if not task_id:
                return None
            source_video_url = await self._poll_video_task(task_id)
            if not source_video_url:
                return None
            video_url = source_video_url
            if store_to_ceph and source_video_url:
                entity_id = related_entity_id or task_id
                video_url, _, _ = await self._store_to_ceph(
                    source_url=source_video_url, media_type="video", content_type="video/mp4",
                    related_entity_type=related_entity_type, related_entity_id=entity_id,
                    user_id=user_id, db_session=db_session)
            return {"status": "completed", "video_url": video_url, "original_url": source_video_url,
                    "task_id": task_id, "message": "Video generated successfully"}
        except Exception as e:
            logger.error(f"视频生成异常: {e}")
            return None

    async def generate_video_from_image(self, image_url: str, prompt: str, **kwargs):
        return await self.generate_video(image_url=image_url, prompt=prompt, **kwargs)


# 全局服务实例
_seedance_service: Optional[SeedanceService] = None

async def get_seedance_service() -> SeedanceService:
    global _seedance_service
    if _seedance_service is None:
        _seedance_service = SeedanceService()
        await _seedance_service.initialize()
    return _seedance_service

async def close_seedance_service():
    global _seedance_service
    if _seedance_service:
        await _seedance_service.close()
        _seedance_service = None
