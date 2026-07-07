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


# 内容审核关键词（用于用户友好错误提示）
_CONTENT_MODERATION_KEYWORDS = [
    "content moderation", "content policy", "safety system",
    "内容审核", "内容安全", "违规内容",
    "not allowed", "inappropriate",
]

_MIN_IMAGE_SIZE = 300  # 最小图像尺寸（像素）


class SeedanceService:
    """Seedance/Seedream AI服务集成（火山引擎 Ark API）

    移植自 moyin-creator 的增强：重试逻辑、图像尺寸检查、内容审核检测
    """

    def __init__(self):
        self.api_url = settings.SEEDANCE_API_URL
        self.api_key = settings.SEEDANCE_API_KEY
        self.model = getattr(settings, 'SEEDANCE_IMAGE_MODEL', 'doubao-seedream-4-5-251128')
        self.video_model = getattr(settings, 'SEEDANCE_VIDEO_MODEL', 'doubao-seedance-2-0-260128')
        self.timeout = settings.SEEDANCE_TIMEOUT
        self._initialized = False
        self._client: Optional[httpx.AsyncClient] = None
        # 重试配置
        self._max_retries: int = 3
        self._retry_delay: float = 2.0

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

    # ---- 重试与错误处理（移植自 moyin-creator） ----

    async def _retry_operation(self, operation, operation_name: str = "API call"):
        """带指数退避的重试封装"""
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                return await operation()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response else 0
                last_error = e
                if status == 429:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(f"{operation_name} 429 限流，{delay:.1f}s 后重试 (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                if status in (500, 502, 503, 529):
                    if attempt < self._max_retries:
                        delay = self._retry_delay * (2 ** attempt)
                        logger.warning(f"{operation_name} {status} 错误，{delay:.1f}s 后重试 (attempt {attempt + 1})")
                        await asyncio.sleep(delay)
                        continue
                raise  # 不可重试的错误
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(f"{operation_name} 异常，{delay:.1f}s 后重试 (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(delay)
                    continue
                raise
        raise last_error or RuntimeError(f"{operation_name} 全部重试失败")

    @staticmethod
    def _check_content_moderation(error_text: str) -> Optional[str]:
        """检测内容审核错误，返回用户友好提示"""
        text_lower = error_text.lower()
        for kw in _CONTENT_MODERATION_KEYWORDS:
            if kw.lower() in text_lower:
                return "内容未通过安全审核，请调整角色描述或画面描述后重试"
        return None

    @staticmethod
    async def _ensure_min_image_size(image_url: str) -> bool:
        """检查图像是否满足最小尺寸要求（>=300px 任一边）"""
        try:
            import io as _io
            from PIL import Image as _Image
            image_bytes = await SeedanceService._download_image_bytes(image_url)
            if not image_bytes:
                return False
            img = _Image.open(_io.BytesIO(image_bytes))
            return img.width >= _MIN_IMAGE_SIZE and img.height >= _MIN_IMAGE_SIZE
        except Exception:
            return True  # 无法检查时假定 OK

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
        height = kwargs.get("height", 1080)  # 16:9 for short drama
        payload = {"model": self.model, "prompt": prompt, "size": f"{width}x{height}", "n": 1, "response_format": "url"}

        async def _call():
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
                        mod_msg = self._check_content_moderation(last_body)
                        if mod_msg:
                            raise RuntimeError(mod_msg)
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
                    raise  # 让 _retry_operation 处理
                except RuntimeError:
                    raise  # 审核错误，不重试
                except Exception as e:
                    last_body = str(e)
            raise RuntimeError(f"图像生成失败: {last_body or 'API无响应'}")

        return await self._retry_operation(_call, "图像生成")

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

    async def generate_image_from_scene(self, scene_description, style="写实风格",
                                         enhance_prompt: bool = True, **kwargs):
        """Generate image from scene description with optional LLM prompt enhancement.

        When enhance_prompt=True (default), uses PromptEnhancer to translate the
        plain description into a professional-grade image generation prompt with
        composition, lighting, color, and quality keywords.

        Falls back to simple "{style}, {description}" if LLM is unavailable.
        """
        if enhance_prompt:
            try:
                from app.services.prompt_enhancer import get_prompt_enhancer
                enhancer = get_prompt_enhancer()
                if enhancer.llm is None:
                    # Try to initialize with a lightweight LLM
                    from app.utils.model_router import create_llm_client
                    enhancer.llm = create_llm_client(prefer="deepseek", timeout=30.0)
                enhanced = await enhancer.enhance(
                    description=scene_description,
                    style=style,
                    scene_type="scene",
                )
                prompt = enhanced.get("image_prompt_zh") or enhanced.get("image_prompt") or f"{style}，{scene_description}"
                logger.debug(f"Prompt enhanced: {len(scene_description)} → {len(prompt)} chars")
            except Exception as e:
                logger.debug(f"Prompt enhancement skipped ({e}), using raw description")
                prompt = f"{style}，{scene_description}" if style else scene_description
        else:
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
        """创建 Seedance 2.0 视频生成任务，返回 task_id（含重试）"""
        if not self.api_key:
            raise ValueError("SEEDANCE_API_KEY 未配置")

        # 检查图像尺寸
        if not await self._ensure_min_image_size(image_url):
            logger.warning(f"图像尺寸不足 (最小 {_MIN_IMAGE_SIZE}px)，可能影响视频生成质量")

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

        async def _call():
            url = f"{self.api_url}/contents/generations/tasks"
            logger.info(f"提交视频任务: model={self.video_model}")
            response = await self._client.post(url, json=payload)
            if response.status_code >= 400:
                mod_msg = self._check_content_moderation(response.text[:800])
                if mod_msg:
                    raise RuntimeError(mod_msg)
                logger.error(f"视频任务创建失败 [{response.status_code}]: {response.text[:800]}")
                raise RuntimeError(f"视频任务创建失败: HTTP {response.status_code}")
            result = response.json()
            task_id = result.get("id")
            logger.info(f"视频任务已创建: {task_id}")
            return task_id

        try:
            return await self._retry_operation(_call, "视频任务提交")
        except Exception as e:
            logger.error(f"视频任务创建异常: {e}")
            return None

    async def _poll_video_task(self, task_id: str) -> Optional[str]:
        """轮询视频任务直到完成，返回 video_url（含状态检测）"""
        url = f"{self.api_url}/contents/generations/tasks/{task_id}"
        # 完成状态列表（移植自 moyin-creator 的多提供商状态映射）
        _SUCCESS_STATUSES = {"succeeded", "completed", "successful"}
        _FAILURE_STATUSES = {"failed", "error", "cancelled", "canceled"}
        for i in range(120):
            try:
                response = await self._client.get(url)
                if response.status_code >= 400:
                    await asyncio.sleep(2)
                    continue
                result = response.json()
                status = result.get("status", "")
                if status in _SUCCESS_STATUSES:
                    video_url = (
                        result.get("content", {}).get("video_url") or
                        result.get("output", {}).get("video_url") or
                        result.get("video_url") or
                        result.get("data", [{}])[0].get("url") if isinstance(result.get("data"), list) else None
                    )
                    if video_url:
                        return video_url
                if status in _FAILURE_STATUSES:
                    error_text = json.dumps(result, ensure_ascii=False)[:500]
                    mod_msg = self._check_content_moderation(error_text)
                    logger.error(f"视频任务失败: {mod_msg or error_text}")
                    return None
                if i % 10 == 0:
                    logger.info(f"视频生成中: {status or 'waiting'} ({i+1}/120)")
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
