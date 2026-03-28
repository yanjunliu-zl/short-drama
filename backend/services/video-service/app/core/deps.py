"""服务依赖"""
from fastapi import Depends, Header, HTTPException
from typing import Optional
from app.middleware.jwt_auth import verify_token, SKIP_AUTH_PATHS
from fastapi import Request

# 缓存服务
_cache_service = None


class CacheService:
    """简单的内存缓存服务实现"""

    def __init__(self):
        self._cache = {}

    async def get(self, key: str):
        return self._cache.get(key)

    async def set(self, key: str, value, expire: int = 3600):
        self._cache[key] = value

    async def delete(self, key: str):
        if key in self._cache:
            del self._cache[key]

    async def is_available(self) -> bool:
        return True


async def get_cache_service() -> CacheService:
    """获取缓存服务"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


async def initialize_cache_service():
    """初始化缓存服务"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> dict:
    """获取当前用户依赖"""
    # 检查是否跳过认证
    for path in SKIP_AUTH_PATHS:
        if request.url.path.startswith(path):
            return None

    # 检查 Authorization 头
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # 验证 token 格式
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


async def require_admin(
    current_user: Optional[dict] = Depends(get_current_user)
) -> dict:
    """要求管理员权限"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # 这里可以添加角色检查逻辑
    return current_user
