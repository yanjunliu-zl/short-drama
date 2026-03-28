from fastapi import APIRouter

from app.api.v1.endpoints import scene

api_router = APIRouter()

api_router.include_router(scene.router, prefix="/scenes", tags=["scenes"])
