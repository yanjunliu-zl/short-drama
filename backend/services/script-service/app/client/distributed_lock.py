"""分布式锁"""
import time
import uuid
from typing import Optional

from redis import Redis
from redis.cluster import RedisCluster

from app.core.config import settings


class DistributedLock:
    """分布式锁实现"""

    def __init__(self, redis_client: Redis, key: str, expiry: int = 30):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.value = str(uuid.uuid4())
        self.expiry = expiry
        self.acquired = False

    def acquire(self) -> bool:
        """获取锁"""
        # 使用SETNX命令
        result = self.redis.set(self.key, self.value, nx=True, ex=self.expiry)
        self.acquired = result is True
        return self.acquired

    def release(self) -> bool:
        """释放锁"""
        if not self.acquired:
            return True

        # 使用Lua脚本保证释放的原子性
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            result = self.redis.eval(script, 1, self.key, self.value)
            self.acquired = result == 0
            return result == 1
        except Exception:
            self.acquired = False
            return False

    def is_acquired(self) -> bool:
        """检查锁是否已获取"""
        return self.acquired


class DistributedLocker:
    """分布式锁管理器"""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def lock(self, key: str, expiry: int = 30) -> Optional[DistributedLock]:
        """获取分布式锁"""
        lock = DistributedLock(self.redis, key, expiry)
        if lock.acquire():
            return lock
        return None


# 全局锁管理器
_locker: Optional[DistributedLocker] = None


def get_locker(redis_client: Redis) -> DistributedLocker:
    """获取分布式锁管理器"""
    global _locker
    if _locker is None:
        _locker = DistributedLocker(redis_client)
    return _locker
