from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import os

from app.core.config import settings
from app.core.logging import setup_structured_logging
from app.middleware.prometheus import MetricsEndpointMiddleware, set_health_status

# 设置结构化日志
setup_structured_logging(settings.PROJECT_NAME, settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 添加中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 可信主机中间件
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# 添加 Prometheus 指标端点
MetricsEndpointMiddleware(app, settings.PROJECT_NAME)

# 健康检查端点
@app.get("/health")
async def health_check():
    set_health_status(settings.PROJECT_NAME, True)
    return {"status": "healthy", "service": "video-service", "timestamp": time.time()}

# 就绪检查端点（用于 Kubernetes）
@app.get("/ready")
async def readiness_check():
    try:
        # 检查依赖服务
        from app.core.deps import get_cache_service
        cache = await get_cache_service()
        if not await cache.is_available():
            set_health_status(settings.PROJECT_NAME, False)
            return JSONResponse(status_code=503, content={"status": "unready", "reason": "cache unavailable"})

        set_health_status(settings.PROJECT_NAME, True)
        return {"status": "ready", "timestamp": time.time()}
    except Exception as e:
        set_health_status(settings.PROJECT_NAME, False)
        return JSONResponse(status_code=503, content={"status": "unready", "reason": str(e)})

# 视频处理端点 - placeholder
@app.get("/api/v1/videos")
async def list_videos():
    return {"videos": []}

@app.post("/api/v1/videos")
async def create_video():
    return {"message": "Video creation endpoint - placeholder", "video_id": "placeholder123"}

@app.get("/api/v1/videos/{video_id}")
async def get_video(video_id: str):
    return {"video_id": video_id, "status": "processing", "progress": 50}

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up video processing service...")
    # 初始化数据库连接
    # 初始化消息队列
    logger.info("Video service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down video processing service...")
    # 清理资源
    logger.info("Video service shutdown completed")
    set_health_status(settings.PROJECT_NAME, False)

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
