"""Prometheus 指标中间件 — recommendation-service"""
import time
import logging
from fastapi import Request, Response, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)
registry = CollectorRegistry()

# HTTP 指标
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code", "service"], registry=registry)
REQUEST_DURATION = Histogram("http_request_duration_seconds", "Request duration", ["method", "endpoint", "service"], buckets=[0.1, 0.5, 1, 2, 5, 10, float("inf")], registry=registry)
INPROGRESS_REQUESTS = Gauge("http_requests_inprogress", "Requests in progress", ["method", "endpoint"], registry=registry)
EXCEPTIONS = Counter("http_exceptions_total", "Total exceptions", ["exception_type", "endpoint", "service"], registry=registry)

# 推荐业务指标
RECOMMENDATION_COUNT = Counter("recommendation_total", "Recommendation requests", ["reason", "status"], registry=registry)
RECOMMENDATION_DURATION = Histogram("recommendation_duration_seconds", "Recommendation pipeline duration", ["stage"], buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5], registry=registry)
HEALTH_STATUS = Gauge("service_health_status", "Health status", ["service"], registry=registry)


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, app_name: str = "recommendation-service"):
        super().__init__(app)
        self.app_name = app_name

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        method, endpoint = request.method, request.url.path
        start_time = time.time()
        INPROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).inc()
        try:
            response = await call_next(request)
            elapsed = time.time() - start_time
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=response.status_code).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(elapsed)
            INPROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).dec()
            response.headers["X-Process-Time"] = str(elapsed)
            return response
        except Exception as e:
            EXCEPTIONS.labels(exception_type=type(e).__name__, endpoint=endpoint).inc()
            INPROGRESS_REQUESTS.labels(method=method, endpoint=endpoint).dec()
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def setup_metrics(app: FastAPI, app_name: str = "storyboard-service"):
    """注册 /metrics 端点和中间件"""
    app.add_middleware(PrometheusMiddleware, app_name=app_name)

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": app_name}

    HEALTH_STATUS.labels(service=app_name).set(1)
