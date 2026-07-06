"""
统一日志配置 - 为 video-service 提供 JSON 格式结构化日志
"""

import logging
import json
import sys
from datetime import datetime
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

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


def setup_logging():
    """设置日志配置 - 结构化 JSON 日志"""

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 控制台处理器 - JSON 格式
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    console_formatter = StructuredJSONFormatter(settings.PROJECT_NAME)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)

    # 避免重复日志
    root_logger.propagate = False

    logging.info("Logging configured with JSON format")


def setup_structured_logging(service_name: str, log_level: str):
    """设置结构化日志 - 带参数版本"""
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 控制台处理器 - JSON 格式
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = StructuredJSONFormatter(service_name)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)

    # 避免重复日志
    root_logger.propagate = False

    logging.info(f"Structured logging configured for {service_name} at level {log_level}")
