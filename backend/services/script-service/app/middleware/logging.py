"""
API 中间件 - 记录请求日志和性能指标
"""

import time
import logging
import uuid
from typing import Callable, Any

from fastapi import Request, Response, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import request_id_var, LoggingContext, get_request_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        with LoggingContext(request_id=request_id, endpoint=request.url.path, method=request.method):
            logger.info(f"Starting request: {request.method} {request.url.path}")

            start_time = time.time()

            try:
                response = await call_next(request)
                process_time = time.time() - start_time
                response.headers["X-Process-Time"] = str(process_time)

                logger.info(
                    f"Completed request: {request.method} {request.url.path} "
                    f"- Status: {response.status_code} - Time: {process_time:.3f}s"
                )

                return response

            except Exception as e:
                process_time = time.time() - start_time

                logger.error(
                    f"Request failed: {request.method} {request.url.path}",
                    extra={"error": str(e), "process_time": process_time}
                )

                return JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error"},
                    headers={"X-Process-Time": str(process_time)},
                )


class PerformanceMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录性能指标"""
        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        if process_time > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} - {process_time:.3f}s"
            )

        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """请求 ID 中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """添加请求 ID 到响应头"""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
