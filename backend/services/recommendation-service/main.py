import logging
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import init_db, close_db
from app.middleware.prometheus import setup_metrics

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

setup_metrics(app, app_name="recommendation-service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start_time)
    return response


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up recommendation service...")
    await init_db()
    from app.services.ranking_model import get_ranking_service
    get_ranking_service()
    logger.info("Recommendation service started (port=%d)", settings.PORT)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down recommendation service...")
    await close_db()
    logger.info("Shutdown complete")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}


app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT,
                reload=settings.DEBUG, log_level=settings.LOG_LEVEL.lower())
