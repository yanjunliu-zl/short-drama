import logging
from typing import Dict, Any, Optional
import hashlib
import json
from datetime import timedelta

from redis.asyncio import Redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class StoryboardCacheService:
    """分镜缓存服务"""

    def __init__(self, redis: Redis):
        self.redis = redis
        self.default_ttl = settings.CACHE_DEFAULT_TTL
        self.storyboard_ttl = settings.CACHE_SCRIPT_TTL  # 分镜缓存2小时

    def _generate_storyboard_key(self, request: Dict[str, Any], prefix: str = "storyboard") -> str:
        """生成分镜缓存键。prefix 区分场景级分镜和镜头级分镜，避免缓存互相覆盖。"""
        key_data = {
            "title": request.get('title', ''),
            "theme": request.get('theme', ''),
            "style": request.get('style', ''),
            "scene_count": request.get('scene_count', 0),
            "script_hash": hashlib.md5(request.get('script', '').encode()).hexdigest()[:16],
            # Shot-level specific fields (empty for scene-level requests)
            "episode_count": request.get('episodeCount', 0),
            "episode_contents_hash": hashlib.md5(
                json.dumps(request.get('episodeContents', []), sort_keys=True).encode()
            ).hexdigest()[:8],
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return f"{prefix}:{hashlib.md5(key_str.encode()).hexdigest()}"

    async def get_cached_storyboard(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取缓存的场景级分镜"""
        try:
            cache_key = self._generate_storyboard_key(request, prefix="storyboard")
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
            return None

    async def cache_storyboard_generation(self, request: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """缓存场景级分镜生成结果"""
        try:
            cache_key = self._generate_storyboard_key(request, prefix="storyboard")
            await self.redis.setex(
                cache_key,
                self.storyboard_ttl,
                json.dumps(data, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.error(f"缓存分镜失败: {e}")
            return False

    async def get_cached_shots(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取缓存的镜头级分镜"""
        try:
            cache_key = self._generate_storyboard_key(request, prefix="shots")
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"获取镜头缓存失败: {e}")
            return None

    async def cache_shots_generation(self, request: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """缓存镜头级分镜生成结果"""
        try:
            cache_key = self._generate_storyboard_key(request, prefix="shots")
            await self.redis.setex(
                cache_key,
                self.storyboard_ttl,
                json.dumps(data, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.error(f"缓存镜头分镜失败: {e}")
            return False


# 全局缓存服务实例
_cache_service: Optional[StoryboardCacheService] = None
_redis_client: Optional[Redis] = None


async def get_storyboard_cache_service() -> StoryboardCacheService:
    """获取分镜缓存服务实例"""
    global _cache_service, _redis_client

    if _cache_service is not None:
        return _cache_service

    try:
        _redis_client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=False
        )
        _cache_service = StoryboardCacheService(_redis_client)
        logger.info("分镜缓存服务初始化成功")
        return _cache_service
    except Exception as e:
        logger.error(f"分镜缓存服务初始化失败: {e}")
        raise


async def close_storyboard_cache_service():
    """关闭分镜缓存服务"""
    global _cache_service, _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        _cache_service = None
        logger.info("分镜缓存服务已关闭")
