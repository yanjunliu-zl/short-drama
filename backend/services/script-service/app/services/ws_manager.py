"""WebSocket 协作管理器 — Redis pub/sub 跨实例广播。

每个 workId 对应一个 Redis channel，所有连接到同一 workId 的
WebSocket 客户端实时接收变更推送。

对标 LibTV 的多人在线协作。
"""
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

WORK_CHANNEL_PREFIX = "collab:work:"
PRESENCE_PREFIX = "collab:presence:"


class WSManager:
    """跨实例 WebSocket 管理器"""

    def __init__(self, redis: Redis):
        self.redis = redis
        self._local: Dict[str, Set[WebSocket]] = {}  # workId → local WS connections
        self._listener_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, ws: WebSocket, work_id: str, user_id: str):
        """客户端连接到某个 workId 的协作频道"""
        await ws.accept()
        if work_id not in self._local:
            self._local[work_id] = set()
            # 启动 Redis pub/sub 监听
            self._listener_tasks[work_id] = asyncio.create_task(
                self._listen_channel(work_id)
            )
        self._local[work_id].add(ws)

        # 广播上线事件
        await self.broadcast(work_id, {
            "type": "presence_join",
            "userId": user_id,
            "timestamp": asyncio.get_event_loop().time(),
        })
        logger.info(f"WS connect: work={work_id} user={user_id} local_clients={len(self._local[work_id])}")

    async def disconnect(self, ws: WebSocket, work_id: str, user_id: str):
        """客户端断开"""
        if work_id in self._local:
            self._local[work_id].discard(ws)
            if not self._local[work_id]:
                del self._local[work_id]
                if work_id in self._listener_tasks:
                    self._listener_tasks[work_id].cancel()
                    del self._listener_tasks[work_id]

        await self.broadcast(work_id, {
            "type": "presence_leave",
            "userId": user_id,
            "timestamp": asyncio.get_event_loop().time(),
        })
        logger.info(f"WS disconnect: work={work_id} user={user_id}")

    async def broadcast(self, work_id: str, message: dict):
        """通过 Redis pub/sub 广播消息到所有实例"""
        channel = f"{WORK_CHANNEL_PREFIX}{work_id}"
        try:
            await self.redis.publish(channel, json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Broadcast failed work={work_id}: {e}")

    async def _listen_channel(self, work_id: str):
        """监听 Redis channel，转发到本地所有客户端"""
        channel = f"{WORK_CHANNEL_PREFIX}{work_id}"
        pubsub = self.redis.pubsub()
        try:
            await pubsub.subscribe(channel)
            async for msg in pubsub.listen():
                if msg["type"] == "message" and work_id in self._local:
                    data = json.loads(msg["data"])
                    dead: list[WebSocket] = []
                    for ws in self._local[work_id]:
                        try:
                            await ws.send_json(data)
                        except Exception:
                            dead.append(ws)
                    for ws in dead:
                        self._local[work_id].discard(ws)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Listener error work={work_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel)

    async def get_presence(self, work_id: str) -> int:
        """获取当前在线人数"""
        return len(self._local.get(work_id, set()))


# Global
_ws_manager: WSManager | None = None


async def get_ws_manager() -> WSManager:
    global _ws_manager
    if _ws_manager is None:
        from app.core.config import settings
        redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=getattr(settings, 'REDIS_DB', 2),
            decode_responses=True,
        )
        _ws_manager = WSManager(redis)
        logger.info("WSManager initialized (Redis pub/sub)")
    return _ws_manager
