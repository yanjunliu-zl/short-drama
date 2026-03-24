import logging
import json
import hashlib
from typing import Any, Optional, Dict, Union
import asyncio
from datetime import timedelta

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis缓存服务，用于缓存AI生成结果和工作流中间数据"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
        self._default_ttl = settings.CACHE_DEFAULT_TTL  # 从配置读取默认缓存时间
        self._cache_enabled = settings.CACHE_ENABLED

    async def connect(self):
        """连接Redis服务器"""
        if self._connected and self.redis_client:
            return

        try:
            logger.info("连接Redis缓存服务...")

            # 构建Redis连接参数
            redis_kwargs = {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "db": settings.REDIS_DB,
                "decode_responses": True,  # 自动解码字符串
            }

            if settings.REDIS_PASSWORD:
                redis_kwargs["password"] = settings.REDIS_PASSWORD

            # 创建异步Redis客户端
            self.redis_client = redis.Redis(**redis_kwargs)

            # 测试连接
            await self.redis_client.ping()
            self._connected = True

            logger.info(f"Redis缓存服务连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

        except Exception as e:
            logger.error(f"Redis缓存服务连接失败: {e}")
            # 连接失败时，将redis_client设为None，后续操作会跳过缓存
            self.redis_client = None
            self._connected = False

    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("Redis缓存服务已断开连接")

    async def is_available(self) -> bool:
        """检查缓存服务是否可用"""
        # 首先检查缓存是否启用
        if not self._cache_enabled:
            return False

        if not self._connected or not self.redis_client:
            return False

        try:
            await self.redis_client.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def _generate_cache_key(self, namespace: str, *args, **kwargs) -> str:
        """生成缓存键

        参数:
            namespace: 缓存命名空间，如 "ai:script"
            args: 位置参数，用于生成哈希
            kwargs: 关键字参数，用于生成哈希

        返回:
            str: 格式为 "namespace:hash" 的缓存键
        """
        # 将所有参数转换为字符串并排序以保证一致性
        parts = []

        # 添加位置参数
        for arg in args:
            if isinstance(arg, (dict, list)):
                parts.append(json.dumps(arg, sort_keys=True))
            else:
                parts.append(str(arg))

        # 添加关键字参数
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            if isinstance(value, (dict, list)):
                parts.append(f"{key}:{json.dumps(value, sort_keys=True)}")
            else:
                parts.append(f"{key}:{str(value)}")

        # 生成哈希
        content = ":".join(parts)
        key_hash = hashlib.md5(content.encode()).hexdigest()

        return f"{namespace}:{key_hash}"

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not await self.is_available():
            return None

        try:
            value = await self.redis_client.get(key)
            if value:
                # 尝试解析JSON
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    # 如果不是JSON，返回原始字符串
                    return value
            return None
        except Exception as e:
            logger.warning(f"获取缓存失败 key={key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        if not await self.is_available():
            return False

        try:
            # 将值转换为JSON字符串
            if isinstance(value, (dict, list, int, float, bool, type(None))):
                value_str = json.dumps(value)
            else:
                value_str = str(value)

            ttl = ttl or self._default_ttl
            await self.redis_client.setex(key, ttl, value_str)
            logger.debug(f"缓存设置成功 key={key}, ttl={ttl}")
            return True
        except Exception as e:
            logger.warning(f"设置缓存失败 key={key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        if not await self.is_available():
            return False

        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"删除缓存失败 key={key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查缓存键是否存在"""
        if not await self.is_available():
            return False

        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.warning(f"检查缓存存在失败 key={key}: {e}")
            return False

    async def clear_namespace(self, namespace: str) -> int:
        """清除指定命名空间的所有缓存"""
        if not await self.is_available():
            return 0

        try:
            pattern = f"{namespace}:*"
            keys = await self.redis_client.keys(pattern)

            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"清除命名空间缓存: {namespace}, 删除 {len(keys)} 个键")
                return len(keys)
            return 0
        except Exception as e:
            logger.warning(f"清除命名空间缓存失败 namespace={namespace}: {e}")
            return 0

    async def get_or_set(self, key: str, func, ttl: Optional[int] = None, *args, **kwargs) -> Any:
        """获取缓存值，如果不存在则调用函数生成并缓存"""
        # 尝试从缓存获取
        cached_value = await self.get(key)
        if cached_value is not None:
            logger.debug(f"缓存命中 key={key}")
            return cached_value

        # 缓存未命中，调用函数生成值
        logger.debug(f"缓存未命中 key={key}, 调用函数生成")
        value = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        # 缓存结果
        if value is not None:
            await self.set(key, value, ttl)

        return value

    # 特定于AI服务的缓存方法

    async def cache_script_generation(self, request: Dict[str, Any], script: str) -> bool:
        """缓存剧本生成结果"""
        key = self._generate_cache_key("ai:script", **request)
        return await self.set(key, script, ttl=settings.CACHE_SCRIPT_TTL)  # 剧本缓存时间从配置读取

    async def get_cached_script(self, request: Dict[str, Any]) -> Optional[str]:
        """获取缓存的剧本生成结果"""
        key = self._generate_cache_key("ai:script", **request)
        return await self.get(key)

    async def cache_script_analysis(self, script_content: str, analysis: Dict[str, Any]) -> bool:
        """缓存剧本分析结果"""
        key = self._generate_cache_key("ai:analysis", script_content)
        return await self.set(key, analysis, ttl=settings.CACHE_ANALYSIS_TTL)  # 分析缓存时间从配置读取

    async def get_cached_analysis(self, script_content: str) -> Optional[Dict[str, Any]]:
        """获取缓存的剧本分析结果"""
        key = self._generate_cache_key("ai:analysis", script_content)
        return await self.get(key)

    async def cache_script_optimization(self, script_content: str, feedback: str, optimized_script: str) -> bool:
        """缓存剧本优化结果"""
        key = self._generate_cache_key("ai:optimization", script_content, feedback=feedback)
        return await self.set(key, optimized_script, ttl=settings.CACHE_OPTIMIZATION_TTL)  # 优化缓存时间从配置读取

    async def get_cached_optimization(self, script_content: str, feedback: str) -> Optional[str]:
        """获取缓存的剧本优化结果"""
        key = self._generate_cache_key("ai:optimization", script_content, feedback=feedback)
        return await self.get(key)

    async def cache_workflow_result(self, request: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """缓存完整工作流结果"""
        key = self._generate_cache_key("workflow:complete", **request)
        return await self.set(key, result, ttl=settings.CACHE_WORKFLOW_TTL)  # 工作流缓存时间从配置读取

    async def get_cached_workflow_result(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取缓存的工作流结果"""
        key = self._generate_cache_key("workflow:complete", **request)
        return await self.get(key)

    async def clear_all_ai_cache(self) -> int:
        """清除所有AI相关缓存"""
        total = 0
        namespaces = ["ai:script", "ai:analysis", "ai:optimization", "workflow:complete"]

        for namespace in namespaces:
            total += await self.clear_namespace(namespace)

        logger.info(f"清除所有AI缓存，共删除 {total} 个键")
        return total


# 全局缓存服务实例
_cache_service_instance: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """获取缓存服务实例（单例模式）"""
    global _cache_service_instance

    if _cache_service_instance is None:
        _cache_service_instance = CacheService()
        await _cache_service_instance.connect()

    return _cache_service_instance


async def initialize_cache_service():
    """初始化缓存服务"""
    await get_cache_service()