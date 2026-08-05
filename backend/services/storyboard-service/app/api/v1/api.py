from fastapi import APIRouter

from app.api.v1.endpoints import storyboard, asset

api_router = APIRouter()

api_router.include_router(storyboard.router, prefix="/storyboard", tags=["storyboard"])
api_router.include_router(asset.router, prefix="/assets", tags=["assets"])
