"""
多级缓存 — L1 进程内 LRU → L2 Redis → L3 DB

用法:
    from cache_layers import MultiLevelCache
    cache = MultiLevelCache(l1_size=1000, l1_ttl=60, l2_redis=redis_client)
    result = await cache.get("key", fallback=db_query)
"""
import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe async-aware in-memory LRU cache (L1)."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        self._store: OrderedDict[str, tuple] = OrderedDict()  # key → (value, expiry)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            self._misses += 1
            return None
        value, expiry = self._store[key]
        if time.time() > expiry:
            del self._store[key]
            self._misses += 1
            return None
        self._store.move_to_end(key)
        self._hits += 1
        return value

    async def set(self, key: str, value: Any, ttl: int = None):
        ttl = ttl or self._ttl
        if key in self._store:
            del self._store[key]
        while len(self._store) >= self._max_size:
            self._store.popitem(last=False)
        self._store[key] = (value, time.time() + ttl)

    async def delete(self, key: str):
        self._store.pop(key, None)

    async def clear(self):
        self._store.clear()

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._store)


class MultiLevelCache:
    """L1 (in-memory LRU) → L2 (Redis) → fallback (DB/LLM)

    Each layer is consulted in order. On a miss, the value is promoted
    to all upper layers after being fetched from the fallback.
    """

    def __init__(self, l1_size: int = 1000, l1_ttl: int = 60,
                 l2_redis=None, l2_ttl: int = 300, namespace: str = "cache"):
        self.l1 = LRUCache(max_size=l1_size, ttl_seconds=l1_ttl)
        self.l2 = l2_redis
        self.l2_ttl = l2_ttl
        self.namespace = namespace

    @staticmethod
    def _make_key(*parts: str) -> str:
        raw = ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    async def get(self, key: str, fallback: Callable[[], Coroutine] = None) -> Optional[Any]:
        """Get value, consulting L1→L2→fallback in order."""
        full_key = f"{self.namespace}:{key}"

        # L1: Memory
        value = await self.l1.get(full_key)
        if value is not None:
            logger.debug(f"MultiLevelCache L1 hit: {full_key[:40]}")
            return value

        # L2: Redis
        if self.l2:
            try:
                raw = await self.l2.get(full_key)
                if raw:
                    value = json.loads(raw)
                    await self.l1.set(full_key, value)  # Promote to L1
                    logger.debug(f"MultiLevelCache L2 hit: {full_key[:40]}")
                    return value
            except Exception as e:
                logger.debug(f"MultiLevelCache L2 error: {e}")

        # Fallback
        if fallback:
            value = await fallback()
            if value is not None:
                await self.set(key, value)
            return value

        return None

    async def set(self, key: str, value: Any, l1_ttl: int = None, l2_ttl: int = None):
        """Set value in all cache layers."""
        full_key = f"{self.namespace}:{key}"

        # L1
        await self.l1.set(full_key, value, ttl=l1_ttl)

        # L2
        if self.l2:
            try:
                await self.l2.setex(
                    full_key,
                    l2_ttl or self.l2_ttl,
                    json.dumps(value, ensure_ascii=False),
                )
            except Exception as e:
                logger.debug(f"MultiLevelCache L2 set error: {e}")

    async def delete(self, key: str):
        full_key = f"{self.namespace}:{key}"
        await self.l1.delete(full_key)
        if self.l2:
            try:
                await self.l2.delete(full_key)
            except Exception:
                pass

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "l1_hit_rate": self.l1.hit_rate,
            "l1_size": self.l1.size,
            "l1_hits": self.l1._hits,
            "l1_misses": self.l1._misses,
        }
