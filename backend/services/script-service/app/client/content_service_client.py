"""Content Service 客户端 — Case CRUD + 用户交互 + 推荐

直连 content-service:8081，不绕 APISIX（内部调用避免被限流）。
失败时优雅降级，不抛出异常。
"""
import logging
import os
from typing import Optional, Dict, Any, List

from app.client.retry_client import RetryClient
from app.client.service_clients import _safe_call

logger = logging.getLogger(__name__)

CONTENT_SERVICE_URL = os.getenv("CONTENT_SERVICE_URL", "http://content-service:8081")


class ContentServiceClient:
    """Content Service HTTP 客户端"""

    def __init__(self):
        self.base_url = CONTENT_SERVICE_URL.rstrip("/")
        self.retry_client = RetryClient(self.base_url)

    # ── Case CRUD ──

    async def list_cases(
        self,
        page: int = 1,
        page_size: int = 10,
        tag: Optional[str] = None,
        sort_by: Optional[str] = "createdAt",
        order: Optional[str] = "desc",
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取案例列表"""
        params = {"page": page, "pageSize": page_size, "sortBy": sort_by, "order": order}
        if tag:
            params["tag"] = tag
        if search:
            params["search"] = search
        result = await _safe_call(
            self.retry_client.get("/api/v1/cases", params=params),
            service_name="content-service",
            fallback={"cases": [], "total": 0, "page": page, "page_size": page_size},
        )
        # content-service returns "pages" (total pages), script-service expects "page_size" (items per page)
        if "pages" in result:
            result.pop("pages")  # remove unused field
        if "page_size" not in result:
            result["page_size"] = page_size  # pass through the original request param
        return result

    async def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """获取案例详情"""
        return await _safe_call(
            self.retry_client.get(f"/api/v1/cases/{case_id}"),
            service_name="content-service",
            fallback=None,
        )

    async def create_case(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建案例"""
        return await _safe_call(
            self.retry_client.post("/api/v1/cases", json=data),
            service_name="content-service",
            fallback=None,
        )

    async def update_case(self, case_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新案例"""
        return await _safe_call(
            self.retry_client.put(f"/api/v1/cases/{case_id}", json=data),
            service_name="content-service",
            fallback=None,
        )

    async def delete_case(self, case_id: str) -> Dict[str, Any]:
        """删除案例"""
        return await _safe_call(
            self.retry_client.delete(f"/api/v1/cases/{case_id}"),
            service_name="content-service",
            fallback={"success": False},
        )

    # ── User Interactions ──

    async def record_view(self, case_id: str) -> Dict[str, Any]:
        """记录浏览"""
        return await _safe_call(
            self.retry_client.post(f"/api/v1/cases/{case_id}/view"),
            service_name="content-service",
            fallback={"success": False},
        )

    async def record_like(self, case_id: str) -> Dict[str, Any]:
        """记录点赞"""
        return await _safe_call(
            self.retry_client.post(f"/api/v1/cases/{case_id}/like"),
            service_name="content-service",
            fallback={"success": False},
        )

    async def record_share(self, case_id: str) -> Dict[str, Any]:
        """记录分享"""
        return await _safe_call(
            self.retry_client.post(f"/api/v1/cases/{case_id}/share"),
            service_name="content-service",
            fallback={"success": False},
        )

    # ── Recommendations & Search ──

    async def get_recommended(
        self, user_id: Optional[str] = None, limit: int = 6
    ) -> Dict[str, Any]:
        """获取推荐案例"""
        params = {"limit": limit}
        if user_id:
            params["userId"] = user_id
        return await _safe_call(
            self.retry_client.get("/api/v1/cases/recommended", params=params),
            service_name="content-service",
            fallback={"cases": [], "total": 0, "reason": "degraded"},
        )

    async def search_cases(
        self,
        q: Optional[str] = None,
        tags: Optional[List[str]] = None,
        genre: Optional[str] = None,
        author: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """搜索案例"""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if q:
            params["q"] = q
        if tags:
            params["tags"] = ",".join(tags)
        if genre:
            params["genre"] = genre
        if author:
            params["author"] = author
        result = await _safe_call(
            self.retry_client.get("/api/v1/cases/search", params=params),
            service_name="content-service",
            fallback={"cases": [], "total": 0, "page": page, "page_size": page_size},
        )
        if "pages" in result:
            result.pop("pages")
        if "page_size" not in result:
            result["page_size"] = page_size
        return result


# 全局单例
_content_service_client: Optional[ContentServiceClient] = None


def get_content_service_client() -> ContentServiceClient:
    """获取全局 ContentServiceClient 实例"""
    global _content_service_client
    if _content_service_client is None:
        _content_service_client = ContentServiceClient()
    return _content_service_client
