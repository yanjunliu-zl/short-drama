# 启动补丁: 修复 langchain_openai + openai SDK http_client 兼容性
from app.patch_startup import apply_patch; apply_patch()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.logging import setup_logging
from app.core.tracing import init_tracing, instrument_fastapi
from app.core.deps import initialize_script_service
from app.core.database import init_db, close_db
from app.services.cache_service import initialize_cache_service
from app.middleware.prometheus import MetricsEndpointMiddleware, set_health_status

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 初始化链路追踪（需在 app 创建前）
init_tracing("script-service")

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

# 添加 Prometheus 指标端点 + HTTP 请求指标记录
from app.middleware.prometheus import PrometheusMiddleware
app.add_middleware(PrometheusMiddleware, app_name=settings.PROJECT_NAME)
MetricsEndpointMiddleware(app, settings.PROJECT_NAME)

# 健康检查端点
@app.get("/health")
async def health_check():
    set_health_status(settings.PROJECT_NAME, True)
    return {"status": "healthy", "timestamp": time.time()}

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

# 注册 FastAPI OpenTelemetry 探针
instrument_fastapi(app)

# 注册API路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up script generation service...")
    # 初始化数据库连接并创建表
    await init_db()
    # 初始化缓存服务
    await initialize_cache_service()
    # 初始化AI模型
    await initialize_script_service()
    # 初始化消息队列
    logger.info("Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down script generation service...")
    # 清理资源
    await close_db()
    logger.info("Service shutdown completed")
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
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
