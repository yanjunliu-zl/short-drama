from fastapi import APIRouter

from app.api.v1.endpoints import script, character, story, health

api_router = APIRouter()

# 注册路由
api_router.include_router(health.router, tags=["health"])
api_router.include_router(script.router, prefix="/scripts", tags=["scripts"])
api_router.include_router(character.router, prefix="/characters", tags=["characters"])
api_router.include_router(story.router, prefix="/stories", tags=["stories"])