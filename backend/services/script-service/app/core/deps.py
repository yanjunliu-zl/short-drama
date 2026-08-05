from app.services.script_service import ScriptService
from app.middleware.jwt_auth import verify_token, SKIP_AUTH_PATHS
from fastapi import Depends, Header, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 全局ScriptService实例
_script_service_instance = None


async def initialize_script_service():
    """初始化剧本服务"""
    global _script_service_instance
    try:
        logger.info("正在初始化剧本服务...")
        _script_service_instance = ScriptService()
        await _script_service_instance.initialize()
        logger.info("剧本服务初始化完成")
    except Exception as e:
        logger.error(f"剧本服务初始化失败: {e}，服务将以降级模式运行")
        # 不抛出异常，允许服务以降级模式启动


def get_script_service() -> ScriptService:
    """获取剧本服务实例"""
    global _script_service_instance

    if _script_service_instance is None:
        logger.warning("ScriptService实例未初始化，创建新实例")
        _script_service_instance = ScriptService()

    return _script_service_instance


async def ensure_script_service_initialized():
    """确保 ScriptService 已初始化 (首次请求时懒加载)"""
    global _script_service_instance
    if _script_service_instance is None:
        _script_service_instance = ScriptService()
    if not _script_service_instance.ai_service._initialized:
        await _script_service_instance.initialize()


async def get_current_user(
    request,
    authorization: Optional[str] = Header(None)
):
    """获取当前用户依赖"""
    # 检查是否跳过认证
    for path in SKIP_AUTH_PATHS:
        if request.url.path.startswith(path):
            return None

    # 检查 Authorization 头
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # 验证 token 格式
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


async def require_admin(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """要求管理员权限"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user
