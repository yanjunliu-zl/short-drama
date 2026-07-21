"""微服务间通信客户端 — 支持优雅降级"""
import asyncio
from typing import Optional, Dict, Any
import aiohttp
from aiohttp import ClientTimeout
from urllib.parse import urljoin
import json
import logging

from app.core.config import settings
from app.client.retry_client import RetryClient

logger = logging.getLogger(__name__)


# 降级标记 — 下游服务不可用时返回此响应
DEGRADED_RESPONSE = {
    "status": "degraded",
    "message": "服务暂时不可用，请稍后重试",
    "degraded": True,
}


async def _safe_call(coro, service_name: str, fallback: Any = None):
    """包装跨服务调用，失败时返回降级响应而非抛出异常。

    Args:
        coro: 异步调用协程。
        service_name: 下游服务名称（用于日志）。
        fallback: 失败时的降级返回值。

    Returns:
        成功时返回 coro 的结果，失败时返回 fallback。
    """
    try:
        return await coro
    except Exception as e:
        logger.warning(f"[DEGRADED] {service_name} 调用失败: {e} — 返回降级响应")
        if fallback is not None:
            return fallback
        return dict(DEGRADED_RESPONSE)


class VideoServiceClient:
    """视频服务客户端"""

    def __init__(self):
        self.base_url = settings.VIDEO_SERVICE_ENDPOINT.rstrip("/")
        self.retry_client = RetryClient(self.base_url)

    async def process_video(
        self,
        task_type: str,
        video_ids: list,
        audio_id: str = None,
        output_format: str = "mp4"
    ) -> Dict[str, Any]:
        """处理视频任务（支持降级）"""
        payload = {"task_type": task_type, "video_ids": video_ids, "audio_id": audio_id, "output_format": output_format}
        return await _safe_call(
            self.retry_client.post("/api/v1/videos/process", json=payload),
            service_name="video-service",
        )

    async def get_video_status(self, task_id: str) -> Dict[str, Any]:
        """获取视频任务状态（支持降级）"""
        return await _safe_call(
            self.retry_client.get(f"/api/v1/videos/{task_id}"),
            service_name="video-service",
            fallback={"status": "unknown", "task_id": task_id, "degraded": True},
        )

    async def get_video(self, video_id: str) -> Dict[str, Any]:
        """获取视频详情（支持降级）"""
        return await _safe_call(
            self.retry_client.get(f"/api/v1/videos/{video_id}"),
            service_name="video-service",
            fallback={"id": video_id, "degraded": True},
        )


class LLMServiceClient:
    """LLM服务客户端"""

    def __init__(self):
        self.base_url = settings.LLMHUA_SERVICE_ENDPOINT.rstrip("/")
        self.retry_client = RetryClient(self.base_url)

    async def generate_content(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None
    ) -> Dict[str, Any]:
        """生成内容"""
        payload = {
            "prompt": prompt,
            "model": model or settings.MODEL_NAME,
            "max_tokens": max_tokens or settings.OPENAI_MAX_TOKENS,
            "temperature": temperature or settings.OPENAI_TEMPERATURE,
        }

        try:
            result = await self.retry_client.post("/api/v1/llmhua/generate", json=payload)
            return result
        except Exception as e:
            logger.error(f"Failed to call LLM service: {e}")
            raise

    async def generate_image(self, prompt: str, style: str = None) -> Dict[str, Any]:
        """生成图像"""
        payload = {
            "prompt": prompt,
            "style": style,
        }

        try:
            result = await self.retry_client.post("/api/v1/llmhua/image", json=payload)
            return result
        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            raise

    async def generate_video(self, image_url: str, prompt: str) -> Dict[str, Any]:
        """从图像生成视频"""
        payload = {
            "image_url": image_url,
            "prompt": prompt,
        }

        try:
            result = await self.retry_client.post("/api/v1/llmhua/video", json=payload)
            return result
        except Exception as e:
            logger.error(f"Failed to generate video: {e}")
            raise


class ScriptServiceClient:
    """剧本服务客户端"""

    def __init__(self):
        self.base_url = settings.SCRIPT_SERVICE_ENDPOINT.rstrip("/")
        self.retry_client = RetryClient(self.base_url)

    async def generate_script(
        self,
        title: str,
        theme: str = None,
        length: str = "短篇",
        style: str = None,
        setting: str = None,
        characters: list = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """生成剧本"""
        payload = {
            "title": title,
            "theme": theme,
            "length": length,
            "style": style,
            "setting": setting,
            "characters": characters or [],
            "user_id": user_id,
        }

        try:
            result = await self.retry_client.post("/api/v1/scripts/generate", json=payload)
            return result
        except Exception as e:
            logger.error(f"Failed to call script service: {e}")
            raise

    async def get_script_status(self, task_id: str) -> Dict[str, Any]:
        """获取剧本生成状态"""
        try:
            result = await self.retry_client.get(f"/api/v1/scripts/{task_id}/status")
            return result
        except Exception as e:
            logger.error(f"Failed to get script status: {e}")
            raise

    async def get_script(self, script_id: str) -> Dict[str, Any]:
        """获取剧本详情"""
        try:
            result = await self.retry_client.get(f"/api/v1/scripts/{script_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to get script: {e}")
            raise

    async def update_script(self, script_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新剧本"""
        try:
            result = await self.retry_client.put(f"/api/v1/scripts/{script_id}", json=data)
            return result
        except Exception as e:
            logger.error(f"Failed to update script: {e}")
            raise


# 全局客户端实例
_video_client: Optional[VideoServiceClient] = None
_llm_client: Optional[LLMServiceClient] = None
_script_client: Optional[ScriptServiceClient] = None


async def get_video_client() -> VideoServiceClient:
    """获取视频服务客户端"""
    global _video_client
    if _video_client is None:
        _video_client = VideoServiceClient()
    return _video_client


async def get_llm_client() -> LLMServiceClient:
    """获取LLM服务客户端"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMServiceClient()
    return _llm_client


async def get_script_client() -> ScriptServiceClient:
    """获取剧本服务客户端"""
    global _script_client
    if _script_client is None:
        _script_client = ScriptServiceClient()
    return _script_client
