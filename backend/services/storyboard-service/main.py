import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.tracing import init_tracing, instrument_fastapi
from app.core.deps import initialize_storyboard_service, close_storyboard_service
from app.core.database import init_db, close_db
from app.middleware.prometheus import setup_metrics

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 初始化链路追踪
init_tracing("storyboard-service")

# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 注册 Prometheus 指标
setup_metrics(app, app_name="storyboard-service")
instrument_fastapi(app)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 中间件：添加处理时间
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up storyboard generation service...")
    await init_db()
    await initialize_storyboard_service()
    logger.info("Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down storyboard generation service...")
    await close_storyboard_service()
    await close_db()
    logger.info("Service shutdown completed")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}


app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
