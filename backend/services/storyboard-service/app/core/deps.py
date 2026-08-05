# 分镜服务依赖注入
from typing import Optional
from app.services.storyboard_service import StoryboardAIService
from app.services.cache_service import get_storyboard_cache_service, close_storyboard_cache_service

# 全局服务实例
_storyboard_service: Optional[StoryboardAIService] = None


async def initialize_storyboard_service():
    """初始化分镜服务"""
    global _storyboard_service

    if _storyboard_service is None:
        _storyboard_service = StoryboardAIService()
        await _storyboard_service.initialize()

    return _storyboard_service


async def get_storyboard_service() -> StoryboardAIService:
    """获取分镜服务实例"""
    if _storyboard_service is None:
        await initialize_storyboard_service()
    return _storyboard_service


async def close_storyboard_service():
    """关闭分镜服务"""
    global _storyboard_service

    if _storyboard_service:
        _storyboard_service = None
        await close_storyboard_cache_service()
