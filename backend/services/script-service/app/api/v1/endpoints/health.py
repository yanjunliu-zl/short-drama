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


@router.get("/metrics")
async def metrics():
    """Prometheus指标端点"""
    # 这里可以添加自定义的业务指标
    # 实际应用中应该使用prometheus_client
    return {
        "requests_total": 0,  # 示例指标
        "errors_total": 0,
        "processing_time_avg": 0,
    }