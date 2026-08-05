from fastapi import APIRouter

from app.api.v1.endpoints import render

api_router = APIRouter()

api_router.include_router(render.router, prefix="/render", tags=["镜头渲染"])
