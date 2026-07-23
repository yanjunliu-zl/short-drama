from fastapi import APIRouter
from app.api.v1.endpoints import recommend

api_router = APIRouter()
api_router.include_router(recommend.router, prefix="/recommendations", tags=["recommendations"])
