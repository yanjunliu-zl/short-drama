from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import os

from app.core.config import settings
from app.services.storage_service import get_storage_service, close_storage_service

# 设置日志
logging.basicConfig(level=logging.INFO)
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

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "scene-extractor", "timestamp": time.time()}

# 导入并包含API路由
from app.api.v1.api import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up scene extractor service...")
    from app.core.database import init_db
    await init_db()
    await get_storage_service()
    logger.info("Scene extractor service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down scene extractor service...")
    await close_storage_service()
    from app.core.database import close_db
    await close_db()
    logger.info("Scene extractor service shutdown completed")

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
