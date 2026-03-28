from fastapi import APIRouter

from app.api.v1.endpoints import storyboard

api_router = APIRouter()

api_router.include_router(storyboard.router, prefix="/storyboard", tags=["storyboard"])
