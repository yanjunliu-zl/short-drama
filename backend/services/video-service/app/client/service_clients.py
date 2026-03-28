"""微服务间通信客户端"""
import asyncio
import logging
from typing import Optional, Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ServiceClient:
    """服务客户端基类"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_retries = settings.RETRY_MAX_ATTEMPTS
        self.backoff_factor = settings.RETRY_BACKOFF_FACTOR
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端（懒加载）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        return self._client

    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """发送请求并处理重试"""
        client = await self._get_client()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {delay}s")
                    await asyncio.sleep(delay)
                    last_exception = e
                else:
                    raise
            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self._calculate_delay(attempt)
                    logger.warning(f"Request error (attempt {attempt + 1}), retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避）"""
        delay = settings.RETRY_INITIAL_DELAY * (settings.RETRY_BACKOFF_FACTOR ** attempt)
        return min(delay, settings.RETRY_MAX_DELAY)

    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送GET请求"""
        response = await self._request_with_retry("GET", endpoint, params=params)
        return response.json()

    async def post(self, endpoint: str, json: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送POST请求"""
        response = await self._request_with_retry("POST", endpoint, json=json)
        return response.json()

    async def put(self, endpoint: str, json: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送PUT请求"""
        response = await self._request_with_retry("PUT", endpoint, json=json)
        return response.json()

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """发送DELETE请求"""
        response = await self._request_with_retry("DELETE", endpoint)
        return response.json()


class VideoServiceClient(ServiceClient):
    """视频服务客户端"""

    def __init__(self):
        super().__init__(settings.VIDEO_SERVICE_ENDPOINT)

    async def process_video(
        self,
        task_type: str,
        video_ids: list,
        audio_id: str = None,
        output_format: str = "mp4"
    ) -> Dict[str, Any]:
        """处理视频任务"""
        payload = {
            "task_type": task_type,
            "video_ids": video_ids,
            "audio_id": audio_id,
            "output_format": output_format,
        }
        return await self.post("/api/v1/videos/process", json=payload)

    async def get_video_status(self, task_id: str) -> Dict[str, Any]:
        """获取视频任务状态"""
        return await self.get(f"/api/v1/videos/{task_id}")

    async def get_video(self, video_id: str) -> Dict[str, Any]:
        """获取视频详情"""
        return await self.get(f"/api/v1/videos/{video_id}")


class ScriptServiceClient(ServiceClient):
    """剧本服务客户端"""

    def __init__(self):
        super().__init__(settings.SCRIPT_SERVICE_ENDPOINT)

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
        return await self.post("/api/v1/scripts/generate", json=payload)

    async def get_script_status(self, task_id: str) -> Dict[str, Any]:
        """获取剧本生成状态"""
        return await self.get(f"/api/v1/scripts/{task_id}/status")

    async def get_script(self, script_id: str) -> Dict[str, Any]:
        """获取剧本详情"""
        return await self.get(f"/api/v1/scripts/{script_id}")

    async def update_script(self, script_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新剧本"""
        return await self.put(f"/api/v1/scripts/{script_id}", json=data)


# 全局客户端实例
_video_client: Optional[VideoServiceClient] = None
_script_client: Optional[ScriptServiceClient] = None


async def get_video_client() -> VideoServiceClient:
    """获取视频服务客户端"""
    global _video_client
    if _video_client is None:
        _video_client = VideoServiceClient()
    return _video_client


async def get_script_client() -> ScriptServiceClient:
    """获取剧本服务客户端"""
    global _script_client
    if _script_client is None:
        _script_client = ScriptServiceClient()
    return _script_client
