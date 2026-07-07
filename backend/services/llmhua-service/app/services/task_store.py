"""分布式任务状态存储 — Redis 后端 (LLMHua Service)"""
import json
import logging
from typing import Dict, Any, Optional, List
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

TASK_PREFIX = "llmhua:task:"
TASK_TTL = 7200  # 2 hours


class TaskStore:
    """Redis-backed task state store for horizontal scaling."""

    def __init__(self, redis: Redis):
        self.redis = redis

    def _key(self, task_id: str) -> str:
        return f"{TASK_PREFIX}{task_id}"

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            data = await self.redis.get(self._key(task_id))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"TaskStore.get failed task_id={task_id}: {e}")
            return None

    async def set(self, task_id: str, data: Dict[str, Any]) -> bool:
        try:
            await self.redis.setex(self._key(task_id), TASK_TTL, json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"TaskStore.set failed task_id={task_id}: {e}")
            return False

    async def create(self, task_id: str, data: Dict[str, Any]) -> bool:
        """Alias for set — create a new task entry."""
        return await self.set(task_id, data)

    async def update(self, task_id: str, partial: Dict[str, Any]) -> bool:
        """Partial update: merge new fields into existing task data."""
        try:
            existing = await self.get(task_id) or {}
            existing.update(partial)
            return await self.set(task_id, existing)
        except Exception as e:
            logger.error(f"TaskStore.update failed task_id={task_id}: {e}")
            return False

    async def delete(self, task_id: str) -> bool:
        try:
            await self.redis.delete(self._key(task_id))
            return True
        except Exception as e:
            logger.error(f"TaskStore.delete failed task_id={task_id}: {e}")
            return False


# Global singleton
_task_store: Optional[TaskStore] = None


async def get_task_store() -> TaskStore:
    global _task_store
    if _task_store is None:
        from app.core.config import settings
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=getattr(settings, 'REDIS_DB', 4),
            decode_responses=True,
        )
        _task_store = TaskStore(redis)
        logger.info("TaskStore initialized (Redis backend, llmhua-service)")
    return _task_store


async def close_task_store():
    global _task_store
    if _task_store and _task_store.redis:
        await _task_store.redis.close()
        _task_store = None
