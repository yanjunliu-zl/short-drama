"""Redis 客户端 — 推荐服务 Bandit 模型存储"""
import logging
import os

import redis.asyncio as redis

logger = logging.getLogger(__name__)

_redis_client = None

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "3"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)


async def get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD or None,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await _redis_client.ping()
            logger.info("Redis connected: %s:%d db=%d", REDIS_HOST, REDIS_PORT, REDIS_DB)
        except Exception as e:
            logger.warning("Redis unavailable, bandit models will be in-memory only: %s", e)
            _redis_client = None
    return _redis_client
