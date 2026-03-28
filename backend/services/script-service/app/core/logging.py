"""
统一日志系统 - 支持 JSON 格式、结构化日志和上下文跟踪
"""

import logging
import sys
import json
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

from app.core.config import settings


# 上下文跟踪 Token
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# 结构化日志格式化器
class StructuredJSONFormatter(logging.Formatter):
    """JSON 格式日志记录器"""

    def __init__(self, service_name: str = "script-service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON"""
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
            "thread_id": record.thread,
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # 添加额外字段
        if hasattr(record, "extra_fields") and record.extra_fields:
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False)


# 文本日志格式化器
class TextFormatter(logging.Formatter):
    """文本格式日志记录器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为文本"""
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        message = f"{timestamp} - {record.name} - {record.levelname} - {record.module}:{record.lineno} - {record.getMessage()}"

        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"

        return message


# 结构化处理器
class StructuredHandler(logging.Handler):
    """结构化日志处理器"""

    def __init__(self, service_name: str = "script-service"):
        super().__init__()
        self.formatter = StructuredJSONFormatter(service_name)

    def emit(self, record: logging.LogRecord) -> None:
        """输出日志"""
        try:
            log_entry = self.format(record)
            print(log_entry, file=sys.stdout)
        except Exception:
            self.handleError(record)


def setup_logging() -> logging.Logger:
    """设置统一日志配置"""

    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 添加结构化处理器（JSON 格式）
    structured_handler = StructuredHandler(settings.PROJECT_NAME)
    structured_handler.setLevel(log_level)
    root_logger.addHandler(structured_handler)

    # 文件处理器（按天滚动）
    if settings.DEBUG:
        file_handler = RotatingFileHandler(
            filename=log_dir / f"{settings.PROJECT_NAME}.log",
            maxBytes=10485760,  # 10MB
            backupCount=10,
        )
    else:
        file_handler = TimedRotatingFileHandler(
            filename=log_dir / f"{settings.PROJECT_NAME}.log",
            when="midnight",
            interval=1,
            backupCount=7,
        )

    file_handler.setLevel(log_level)
    file_handler.setFormatter(TextFormatter())
    root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.INFO)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)

    # 避免重复日志
    root_logger.propagate = False

    logger = logging.getLogger(settings.PROJECT_NAME)
    logger.info(f"Logging configured - level: {settings.LOG_LEVEL}, debug: {settings.DEBUG}")

    return logger


# 上下文管理器
class LoggingContext:
    """日志上下文管理器"""

    def __init__(self, **kwargs):
        self.extra_fields = kwargs
        self.token = None

    def __enter__(self):
        # 设置请求 ID
        if "request_id" not in self.extra_fields:
            self.extra_fields["request_id"] = str(uuid.uuid4())
        self.token = request_id_var.set(self.extra_fields["request_id"])
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            request_id_var.reset(self.token)
        return False

    def update(self, **kwargs):
        """更新上下文字段"""
        self.extra_fields.update(kwargs)
        return self

    def bind(self, **kwargs):
        """绑定额外字段"""
        return self.update(**kwargs)

    def get_request_id(self) -> str:
        """获取请求 ID"""
        return request_id_var.get()


# 日志工具函数
def get_request_id() -> str:
    """获取当前请求 ID"""
    return request_id_var.get()


def set_request_id(request_id: str):
    """设置当前请求 ID"""
    request_id_var.set(request_id)


def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs):
    """带上下文的日志记录"""
    extra = {"extra_fields": kwargs} if kwargs else {}
    getattr(logger, level)(message, extra=extra)


def error_with_traceback(logger: logging.Logger, message: str, exc: Exception):
    """记录带堆栈信息的错误"""
    logger.error(
        message,
        extra={
            "extra_fields": {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            }
        },
    )


# 配置日志
logger = setup_logging()
