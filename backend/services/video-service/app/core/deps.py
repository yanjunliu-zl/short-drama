"""服务依赖"""
import json
import logging
from typing import Optional
from fastapi import Depends, Header, HTTPException, Request
from redis.asyncio import Redis
from app.middleware.jwt_auth import verify_token, SKIP_AUTH_PATHS

logger = logging.getLogger(__name__)

# 缓存服务
_cache_service: Optional["CacheService"] = None


class CacheService:
    """Redis 缓存服务 — 支持水平扩展，替换内存 dict"""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def get(self, key: str):
        try:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error(f"CacheService.get 失败 key={key}: {e}")
            return None

    async def set(self, key: str, value, expire: int = 3600):
        try:
            await self._redis.setex(key, expire, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.error(f"CacheService.set 失败 key={key}: {e}")

    async def delete(self, key: str):
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.error(f"CacheService.delete 失败 key={key}: {e}")

    async def is_available(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False

    async def close(self):
        await self._redis.close()


async def get_cache_service() -> CacheService:
    """获取缓存服务（延迟初始化 Redis 连接）"""
    global _cache_service
    if _cache_service is None:
        from app.core.config import settings
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        _cache_service = CacheService(redis)
        logger.info("CacheService 已初始化 (Redis 后端, db=%d)", settings.REDIS_DB)
    return _cache_service


async def initialize_cache_service():
    """初始化缓存服务"""
    await get_cache_service()


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
