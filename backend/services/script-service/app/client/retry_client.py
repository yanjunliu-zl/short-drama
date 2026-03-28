"""HTTP 重试客户端"""
import asyncio
import time
from typing import Optional, Dict, Any
import aiohttp
from aiohttp import ClientTimeout
from urllib.parse import urljoin

from app.core.config import settings


class RetryClient:
    """支持重试的 HTTP 客户端"""

    def __init__(self, base_url: str = ""):
        self.base_url = base_url.rstrip("/")
        self.max_attempts = settings.RETRY_MAX_ATTEMPTS
        self.initial_delay = settings.RETRY_INITIAL_DELAY
        self.max_delay = settings.RETRY_MAX_DELAY
        self.backoff_factor = settings.RETRY_BACKOFF_FACTOR

    def _calculate_delay(self, attempt: int) -> float:
        """计算重试延迟时间（指数退避）"""
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)

    async def _request_with_retry(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """发送请求并处理重试"""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                timeout = ClientTimeout(total=settings.RESPONSE_TIMEOUT)
                async with session.request(
                    method,
                    url,
                    timeout=timeout,
                    **kwargs
                ) as response:
                    # 检查响应状态
                    if response.status >= 500:
                        if attempt < self.max_attempts - 1:
                            delay = self._calculate_delay(attempt)
                            await asyncio.sleep(delay)
                            continue
                        response.raise_for_status()
                    return response

            except aiohttp.ClientError as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_exception

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """发送 GET 请求"""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))

        async with aiohttp.ClientSession() as session:
            async with await self._request_with_retry(
                session, "GET", url, params=params
            ) as response:
                return await response.json()

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """发送 POST 请求"""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))

        async with aiohttp.ClientSession() as session:
            async with await self._request_with_retry(
                session, "POST", url, data=data, json=json
            ) as response:
                return await response.json()

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """发送 PUT 请求"""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))

        async with aiohttp.ClientSession() as session:
            async with await self._request_with_retry(
                session, "PUT", url, data=data, json=json
            ) as response:
                return await response.json()

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """发送 DELETE 请求"""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))

        async with aiohttp.ClientSession() as session:
            async with await self._request_with_retry(
                session, "DELETE", url
            ) as response:
                return await response.json()


# 全局重试客户端实例
script_service_client = RetryClient(base_url="")
video_service_client = RetryClient(base_url="")
llmhua_service_client = RetryClient(base_url="")
