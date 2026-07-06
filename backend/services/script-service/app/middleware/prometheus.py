"""
Prometheus 指标中间件 - 为 FastAPI 应用提供 Prometheus 监控指标
"""

import time
import logging
from typing import Callable, Optional

from fastapi import Request, Response, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    push_to_gateway,
)

logger = logging.getLogger(__name__)

# 创建自定义注册表
registry = CollectorRegistry()

# 定义指标

# ── AI 用量业务指标 ──
script_generation_tokens = Counter(
    'script_generation_tokens_total',
    'Total LLM tokens consumed by script generation',
    ['token_type', 'service'],
    registry=registry,
)
script_generation_cost = Counter(
    'script_generation_cost_estimate_total',
    'Total estimated cost of script generation (CNY)',
    ['service'],
    registry=registry,
)

# ── HTTP 和应用指标 ──
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")],
    registry=registry,
)

REQUEST_SIZE = Histogram(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=[100, 1000, 5000, 10000, 50000, 100000, float("inf")],
    registry=registry,
)

RESPONSE_SIZE = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=[100, 1000, 5000, 10000, 50000, 100000, float("inf")],
    registry=registry,
)

INPROGRESS_REQUESTS = Gauge(
    "http_requests_inprogress",
    "Number of HTTP requests in progress",
    ["method", "endpoint"],
    registry=registry,
)

EXCEPTIONS = Counter(
    "http_exceptions_total",
    "Total number of exceptions",
    ["exception_type", "endpoint"],
    registry=registry,
)

# 自定义业务指标
SCRIPT_GENERATION_COUNT = Counter(
    "script_generation_total",
    "Total number of script generations",
    ["script_type", "status"],
    registry=registry,
)

SCRIPT_DURATION = Histogram(
    "script_generation_duration_seconds",
    "Script generation duration in seconds",
    ["script_type"],
    buckets=[10, 30, 60, 120, 300, 600, float("inf")],
    registry=registry,
)

VIDEO_PROCESSING_COUNT = Counter(
    "video_processing_total",
    "Total number of video processing tasks",
    ["status"],
    registry=registry,
)

# 上下文变量存储请求信息
_request_info: dict = {}


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Prometheus 指标中间件"""

    def __init__(self, app: ASGIApp, app_name: str = "script-service"):
        super().__init__(app)
        self.app_name = app_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并收集指标"""
        # 跳过 Prometheus 自身的指标端点
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = request.url.path
        start_time = time.time()

        # 增加请求数和进行中的请求数
        INPROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).inc()

        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 更新指标
            REQUEST_COUNT.labels(
                method=method, endpoint=endpoint, status_code=response.status_code
            ).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(process_time)
            # StreamingResponse has no .body; use Content-Length header or 0
            try:
                resp_body_len = len(response.body) if hasattr(response, 'body') else (
                    int(response.headers.get('content-length', 0)) if hasattr(response, 'headers') else 0
                )
            except Exception:
                resp_body_len = 0
            RESPONSE_SIZE.labels(method=method, endpoint=endpoint).observe(resp_body_len)
            INPROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).dec()

            # 设置响应头
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Prometheus-Scrape"] = "true"

            return response

        except Exception as e:
            process_time = time.time() - start_time

            # 记录异常
            EXCEPTIONS.labels(
                exception_type=type(e).__name__, endpoint=endpoint
            ).inc()
            INPROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).dec()

            logger.error(f"Request failed: {method} {endpoint} - {e}")

            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Process-Time": str(process_time)},
            )


class MetricsEndpointMiddleware:
    """提供 /metrics 端点的中间件"""

    def __init__(self, app: FastAPI, app_name: str = "script-service"):
        self.app = app
        self.app_name = app_name
        self._setup_metrics_endpoint()

    def _setup_metrics_endpoint(self):
        """设置 /metrics 端点"""

        @self.app.get("/metrics")
        async def metrics():
            """Prometheus 指标端点"""
            return Response(
                content=generate_latest(registry),
                media_type=CONTENT_TYPE_LATEST,
            )


# 业务指标记录器
class BusinessMetrics:
    """业务指标记录器"""

    @staticmethod
    def record_script_generation(script_type: str, status: str, duration: float):
        """记录剧本生成指标"""
        SCRIPT_GENERATION_COUNT.labels(script_type=script_type, status=status).inc()
        SCRIPT_DURATION.labels(script_type=script_type).observe(duration)

    @staticmethod
    def record_video_processing(status: str):
        """记录视频处理指标"""
        VIDEO_PROCESSING_COUNT.labels(status=status).inc()


# Pushgateway 支持
async def push_metrics_to_gateway(gateway_url: str, job_name: str):
    """推送到 Pushgateway"""
    try:
        push_to_gateway(
            gateway_url=gateway_url,
            job=job_name,
            registry=registry,
        )
        logger.info(f"Pushed metrics to {gateway_url}")
    except Exception as e:
        logger.error(f"Failed to push metrics: {e}")


# 健康检查指标
HEALTH_STATUS = Gauge(
    "service_health_status",
    "Service health status (1 = healthy, 0 = unhealthy)",
    ["service"],
    registry=registry,
)


def set_health_status(service: str, is_healthy: bool):
    """设置服务健康状态"""
    status = 1 if is_healthy else 0
    HEALTH_STATUS.labels(service=service).set(status)
