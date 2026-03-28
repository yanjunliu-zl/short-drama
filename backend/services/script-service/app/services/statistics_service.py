"""
数据统计分析服务 - 收集和分析服务运行指标
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import json

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"      # 累加器
    GAUGE = "gauge"          # 仪表盘
    HISTOGRAM = "histogram"  # 直方图
    SUMMARY = "summary"      # 摘要


@dataclass
class Metric:
    """指标数据"""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metric_type: str = MetricType.GAUGE.value


@dataclass
class RequestStats:
    """请求统计"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_processing_time: float = 0.0
    slow_requests: int = 0
    endpoints: Dict[str, Dict[str, Any]] = field(default_factory=lambda: defaultdict(dict))


class StatisticsCollector:
    """统计收集器 - 收集和聚合指标数据"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
        self.request_stats = RequestStats()
        self.endpoint_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "total_time": 0.0, "min_time": float("inf"), "max_time": 0.0}
        )
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.metric_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    async def connect(self):
        """连接 Redis"""
        if self._connected:
            return

        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=1,  # 使用 DB 1 存储统计信息
                decode_responses=True,
                password=settings.REDIS_PASSWORD or None,
            )

            await self.redis_client.ping()
            self._connected = True
            logger.info("Statistics collector connected to Redis")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False

    async def disconnect(self):
        """断开 Redis 连接"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("Statistics collector disconnected from Redis")

    async def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        processing_time: float,
        error: Optional[str] = None,
    ):
        """记录请求统计"""
        if not self._connected:
            return

        try:
            # 更新总统计
            self.request_stats.total_requests += 1
            self.request_stats.total_processing_time += processing_time

            if status_code >= 500:
                self.request_stats.failed_requests += 1
                if error:
                    self.error_counts[error] += 1
            else:
                self.request_stats.successful_requests += 1

            if processing_time > 1.0:
                self.request_stats.slow_requests += 1

            # 更新端点统计
            endpoint_key = f"{method}:{endpoint}"
            self.endpoint_metrics[endpoint_key]["count"] += 1
            self.endpoint_metrics[endpoint_key]["total_time"] += processing_time
            self.endpoint_metrics[endpoint_key]["min_time"] = min(
                self.endpoint_metrics[endpoint_key]["min_time"], processing_time
            )
            self.endpoint_metrics[endpoint_key]["max_time"] = max(
                self.endpoint_metrics[endpoint_key]["max_time"], processing_time
            )

            # 写入 Redis
            await self._record_request_redis(
                endpoint_key, status_code, processing_time, error
            )

        except Exception as e:
            logger.error(f"Failed to record request: {e}")

    async def _record_request_redis(
        self,
        endpoint_key: str,
        status_code: int,
        processing_time: float,
        error: Optional[str],
    ):
        """记录请求到 Redis"""
        now = datetime.utcnow()
        date_key = now.strftime("%Y-%m-%d")
        hour_key = now.strftime("%Y-%m-%d:%H")

        # 管道操作
        pipe = self.redis_client.pipeline()

        # 按日期统计
        pipe.hincrby(f"stats:requests:by_date:{date_key}", endpoint_key, 1)

        # 按小时统计
        pipe.hincrby(f"stats:requests:by_hour:{hour_key}", endpoint_key, 1)

        # 按状态码统计
        pipe.hincrby(f"stats:requests:by_status:{date_key}", str(status_code), 1)

        # 端点响应时间
        pipe.rpush(f"stats:response_time:{endpoint_key}:{date_key}", processing_time)
        pipe.expire(f"stats:response_time:{endpoint_key}:{date_key}", 7 * 24 * 3600)

        # 错误统计
        if error:
            pipe.hincrby(f"stats:errors:by_date:{date_key}", error, 1)

        # 全局计数器
        pipe.incr("stats:total_requests")
        pipe.incr(f"stats:requests:by_status:all:{status_code}")

        await pipe.execute()

    async def record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        metric_type: str = MetricType.GAUGE.value,
    ):
        """记录自定义指标"""
        if not self._connected:
            return

        try:
            timestamp = datetime.utcnow().isoformat()
            metric_data = json.dumps({
                "name": name,
                "value": value,
                "labels": labels or {},
                "timestamp": timestamp,
                "type": metric_type,
            })

            # 发布到 Redis Stream
            await self.redis_client.xadd(
                f"metrics:{name}",
                {"data": metric_data},
                maxlen=10000,  # 保留最近 10000 条
            )

        except Exception as e:
            logger.error(f"Failed to record metric: {e}")

    async def get_request_stats(self, period: str = "today") -> Dict[str, Any]:
        """获取请求统计"""
        if not self._connected:
            return {"error": "Redis not connected"}

        try:
            date_key = datetime.utcnow().strftime("%Y-%m-%d")

            if period == "today":
                # 从内存获取实时统计
                return {
                    "total_requests": self.request_stats.total_requests,
                    "successful_requests": self.request_stats.successful_requests,
                    "failed_requests": self.request_stats.failed_requests,
                    "avg_processing_time": (
                        self.request_stats.total_processing_time / self.request_stats.total_requests
                        if self.request_stats.total_requests > 0 else 0
                    ),
                    "slow_requests": self.request_stats.slow_requests,
                }
            else:
                # 从 Redis 获取历史统计
                stats = {
                    "period": period,
                    "date": date_key,
                }

                # 获取总请求数
                total = await self.redis_client.get("stats:total_requests")
                stats["total_requests"] = int(total) if total else 0

                # 获取状态码分布
                status_counts = await self.redis_client.hgetall(f"stats:requests:by_status:{date_key}")
                stats["status_codes"] = {k: int(v) for k, v in status_counts.items()}

                return stats

        except Exception as e:
            logger.error(f"Failed to get request stats: {e}")
            return {"error": str(e)}

    async def get_endpoint_stats(self, period: str = "today") -> Dict[str, Any]:
        """获取端点统计"""
        if not self._connected:
            return {"error": "Redis not connected"}

        try:
            date_key = datetime.utcnow().strftime("%Y-%m-%d")
            stats = {}

            # 从内存获取端点统计
            for endpoint, metrics in self.endpoint_metrics.items():
                if metrics["count"] > 0:
                    stats[endpoint] = {
                        "count": metrics["count"],
                        "avg_time": metrics["total_time"] / metrics["count"],
                        "min_time": metrics["min_time"],
                        "max_time": metrics["max_time"],
                    }

            return {"endpoints": stats}

        except Exception as e:
            logger.error(f"Failed to get endpoint stats: {e}")
            return {"error": str(e)}

    async def get_error_stats(self, period: str = "today") -> Dict[str, int]:
        """获取错误统计"""
        if not self._connected:
            return {}

        try:
            date_key = datetime.utcnow().strftime("%Y-%m-%d")
            errors = await self.redis_client.hgetall(f"stats:errors:by_date:{date_key}")
            return {k: int(v) for k, v in errors.items()}

        except Exception as e:
            logger.error(f"Failed to get error stats: {e}")
            return {}

    async def get_metrics(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指标历史数据"""
        if not self._connected:
            return []

        try:
            metrics = await self.redis_client.xrevrange(
                f"metrics:{name}",
                count=limit
            )

            result = []
            for _, data in metrics:
                result.append(json.loads(data["data"]))

            return result

        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return []


# 全局实例
_statistics_collector: Optional[StatisticsCollector] = None


async def get_statistics_collector() -> StatisticsCollector:
    """获取统计收集器实例"""
    global _statistics_collector

    if _statistics_collector is None:
        _statistics_collector = StatisticsCollector()
        await _statistics_collector.connect()

    return _statistics_collector


async def record_request_stats(
    endpoint: str,
    method: str,
    status_code: int,
    processing_time: float,
    error: Optional[str] = None,
):
    """记录请求统计（便捷函数）"""
    collector = await get_statistics_collector()
    await collector.record_request(endpoint, method, status_code, processing_time, error)


async def record_custom_metric(
    name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
):
    """记录自定义指标（便捷函数）"""
    collector = await get_statistics_collector()
    await collector.record_metric(name, value, labels)
