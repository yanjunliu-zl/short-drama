from fastapi import APIRouter

from app.api.v1.endpoints import script, health, case, work

api_router = APIRouter()

# 注册路由
api_router.include_router(health.router, tags=["health"])
api_router.include_router(script.router, prefix="/scripts", tags=["scripts"])
api_router.include_router(case.router, prefix="/cases", tags=["cases"])
api_router.include_router(work.router, prefix="/works", tags=["works"])