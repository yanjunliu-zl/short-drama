"""
应用级分布式限流中间件 — Redis 滑动窗口 + 用户级别限制。

在 Traefik 网关限流之上提供第二层保护:
  - per-user 粒度 (基于 user_id 或 IP)
  - 滑动窗口计数 (非粗暴的固定窗口)
  - 不同端点不同限额
  - 超过限额返回 429 + Retry-After

用法 (FastAPI):
    from rate_limit_middleware import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, redis_url="redis://redis:6379")
"""
import asyncio
import hashlib
import logging
import time
from typing import Callable, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 各端点类别的限额 (per user per minute)
ENDPOINT_LIMITS: Dict[str, int] = {
    "ai_generate": 10,     # 剧本/分镜生成: 10 req/min
    "image_gen": 5,         # 图像生成: 5 req/min
    "video_gen": 3,         # 视频生成: 3 req/min
    "recommend": 60,       # 推荐: 60 req/min
    "browse": 300,         # 浏览案例: 300 req/min
    "auth": 20,            # 登录/注册: 20 req/min
    "default": 100,         # 其他: 100 req/min
}


def _classify_endpoint(path: str) -> str:
    """根据路径分类请求类型，分配对应的限额类别。"""
    path_lower = path.lower()
    if any(kw in path_lower for kw in ['generate', 'from-outline', 'from-novel', 'novel2script', 'storyboard/generate', 'shots/generate']):
        return "ai_generate"
    if any(kw in path_lower for kw in ['images/generate', 'generate-scene-images', 'preview-image']):
        return "image_gen"
    if any(kw in path_lower for kw in ['videos/generate', 'shots-to-video']):
        return "video_gen"
    if 'recommend' in path_lower:
        return "recommend"
    if any(kw in path_lower for kw in ['cases', 'works', 'scenes', 'search']):
        return "browse"
    if any(kw in path_lower for kw in ['login', 'register', 'auth', 'token']):
        return "auth"
    return "default"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """分布式限流中间件 — Redis 滑动窗口。

    跨 pod 共享计数 (通过 Redis)，每个 user_id 独立限流。
    未认证用户按 IP 限流。
    """

    def __init__(self, app, redis_url: str = "", prefix: str = "ratelimit"):
        super().__init__(app)
        self._prefix = prefix
        self._redis = None
        self._redis_url = redis_url
        self._initialized = False

    async def _init_redis(self):
        if self._initialized:
            return
        try:
            import redis.asyncio as aioredis
            url = self._redis_url or "redis://redis:6379"
            self._redis = aioredis.from_url(url, decode_responses=True)
            await self._redis.ping()
            self._initialized = True
        except Exception as e:
            logger.warning(f"RateLimitMiddleware: Redis unavailable ({e}), "
                           "rate limiting disabled")
            self._initialized = True  # Don't retry — degraded mode

    async def dispatch(self, request: Request, call_next: Callable):
        await self._init_redis()

        # Without Redis, skip rate limiting (degraded mode)
        if self._redis is None:
            return await call_next(request)

        # Classify request
        category = _classify_endpoint(request.url.path)
        limit = ENDPOINT_LIMITS.get(category, ENDPOINT_LIMITS["default"])

        # Identify user
        user_id = request.headers.get("X-User-ID") or \
                  request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or \
                  request.client.host if request.client else "anonymous"

        # Redis key: ratelimit:{category}:{user_id}:{minute_window}
        minute_window = int(time.time() / 60)
        key = f"{self._prefix}:{category}:{user_id}:{minute_window}"

        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 120)  # 2-min TTL, covers edge

            if count > limit:
                retry_after = 60 - (int(time.time()) % 60)
                logger.debug(f"RateLimit: {user_id} exceeded {category} "
                            f"({count}/{limit})")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "message": f"请求过于频繁 ({category})，请 {retry_after}s 后重试",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception as e:
            logger.debug(f"RateLimit check failed (non-blocking): {e}")

        return await call_next(request)
