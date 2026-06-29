"""统一 JSON 日志 — scene-extractor"""
import logging
import sys
import json
import os
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str = "scene-extractor"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    log_level = os.getenv("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter("scene-extractor"))
    root.addHandler(handler)

    for name in ("uvicorn", "uvicorn.error", "sqlalchemy", "sqlalchemy.engine",
                 "httpx", "httpcore", "redis", "fastapi", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    logger = logging.getLogger("scene-extractor")
    logger.info(f"JSON logging configured level={log_level}")
    return logger


logger = setup_logging()
