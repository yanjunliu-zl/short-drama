from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
import psutil
import time

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": time.time()
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """详细健康检查"""
    # 检查系统资源
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": time.time(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available": memory.available,
            "memory_total": memory.total,
            "disk_percent": disk.percent,
            "disk_free": disk.free,
            "disk_total": disk.total,
        },
        "dependencies": {
            "database": "connected",  # 实际应检查数据库连接
            "redis": "connected",     # 实际应检查Redis连接
            "rabbitmq": "connected",  # 实际应检查RabbitMQ连接
        }
    }


# Prometheus 指标由 prometheus_client 中间件自动提供，不在此处定义
# 指标暴露在: /metrics (由 setup_metrics 中间件处理)