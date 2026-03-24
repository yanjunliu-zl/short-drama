from app.services.script_service import ScriptService
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
        logger.error(f"剧本服务初始化失败: {e}")
        raise


def get_script_service() -> ScriptService:
    """获取剧本服务实例"""
    global _script_service_instance

    if _script_service_instance is None:
        logger.warning("ScriptService实例未初始化，创建新实例（这通常应在应用启动时初始化）")
        _script_service_instance = ScriptService()

    return _script_service_instance