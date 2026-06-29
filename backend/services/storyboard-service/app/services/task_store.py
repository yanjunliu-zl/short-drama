"""分布式任务状态存储 — Redis 后端，支持多实例水平扩展"""
import json
import logging
from typing import Dict, Any, Optional, List
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

TASK_PREFIX = "storyboard:task:"
TASK_TTL = 7200  # 任务状态保留 2 小时


class TaskStore:
    """Redis 任务状态存储，替换内存 dict，支持水平扩展"""

    def __init__(self, redis: Redis):
        self.redis = redis

    def _key(self, task_id: str) -> str:
        return f"{TASK_PREFIX}{task_id}"

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            data = await self.redis.get(self._key(task_id))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"TaskStore.get 失败 task_id={task_id}: {e}")
            return None

    async def set(self, task_id: str, data: Dict[str, Any]) -> bool:
        try:
            await self.redis.setex(self._key(task_id), TASK_TTL, json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"TaskStore.set 失败 task_id={task_id}: {e}")
            return False

    async def delete(self, task_id: str) -> bool:
        try:
            await self.redis.delete(self._key(task_id))
            return True
        except Exception as e:
            logger.error(f"TaskStore.delete 失败 task_id={task_id}: {e}")
            return False

    async def list_completed(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出已完成的任务（用于列表查询）"""
        try:
            keys = []
            cursor = 0
            while True:
                cursor, batch = await self.redis.scan(cursor, match=f"{TASK_PREFIX}*", count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            tasks = []
            for key in keys[:limit * 2]:  # 多取一些，过滤后取 limit
                data = await self.redis.get(key)
                if data:
                    task = json.loads(data)
                    if task.get("status") == "completed":
                        tasks.append(task)

            tasks.sort(key=lambda t: t.get("end_time", 0), reverse=True)
            return tasks[:limit]
        except Exception as e:
            logger.error(f"TaskStore.list_completed 失败: {e}")
            return []


# 全局单例
_task_store: Optional[TaskStore] = None


async def get_task_store() -> TaskStore:
    global _task_store
    if _task_store is None:
        from app.core.config import settings
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        _task_store = TaskStore(redis)
        logger.info("TaskStore 已初始化 (Redis 后端)")
    return _task_store
