"""
结构化日志中间件 - 为 FastAPI 应用提供 JSON 格式日志
"""

import time
import logging
import json
import sys
from typing import Callable
from datetime import datetime
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# 请求 ID 上下文变量
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class StructuredJSONFormatter(logging.Formatter):
    """JSON 格式的结构化日志格式器"""

    def __init__(self, service_name: str = "video-service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "request_id": request_id_var.get(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加自定义字段
        if hasattr(record, "custom_fields") and record.custom_fields:
            log_data.update(record.custom_fields)

        return json.dumps(log_data, ensure_ascii=False)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    def __init__(self, app: ASGIApp, service_name: str = "video-service"):
        super().__init__(app)
        self.service_name = service_name
        self.logger = logging.getLogger(f"{service_name}.requests")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        # 生成请求 ID
        request_id = f"{datetime.utcnow().timestamp()}-{id(request)}"
        request_id_var.set(request_id)

        # 记录请求开始
        self.logger.info(
            f"{request.method} {request.url.path}",
            extra={"custom_fields": {"event": "request_start", "request_id": request_id}}
        )

        start_time = time.time()

        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 添加响应头
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = request_id

            # 记录请求完成
            self.logger.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    "custom_fields": {
                        "event": "request_complete",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "process_time_seconds": process_time,
                    }
                }
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time

            # 记录异常
            self.logger.error(
                f"{request.method} {request.url.path} - Exception: {str(e)}",
                extra={
                    "custom_fields": {
                        "event": "request_error",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(e),
                        "process_time_seconds": process_time,
                    }
                },
                exc_info=True
            )

            raise


class PerformanceMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录性能指标"""
        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time

        # 性能日志（使用特定日志级别控制）
        if process_time > 5.0:
            logging.getLogger("performance.slow").warning(
                f"Slow request: {request.method} {request.url.path} - {process_time:.3f}s"
            )
        elif process_time > 1.0:
            logging.getLogger("performance.warning").info(
                f"Slow request: {request.method} {request.url.path} - {process_time:.3f}s"
            )

        response.headers["X-Process-Time"] = str(process_time)

        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """请求 ID 中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """为每个请求生成并设置请求 ID"""
        request_id = f"{datetime.utcnow().timestamp()}-{id(request)}"
        request_id_var.set(request_id)

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        return response


def setup_structured_logging(service_name: str = "video-service", log_level: str = "INFO"):
    """设置结构化日志"""

    # 创建处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredJSONFormatter(service_name))

    # 创建性能日志处理器（单独输出到文件）
    perf_handler = logging.StreamHandler(sys.stdout)
    perf_handler.setFormatter(StructuredJSONFormatter(service_name))

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.getLevelName(log_level))
    root_logger.addHandler(console_handler)

    # 配置请求日志器
    request_logger = logging.getLogger(f"{service_name}.requests")
    request_logger.setLevel(logging.INFO)

    # 配置性能日志器
    perf_logger = logging.getLogger("performance")
    perf_logger.setLevel(logging.DEBUG)

    # 第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return root_logger


def get_request_id() -> str:
    """获取当前请求 ID"""
    return request_id_var.get()
