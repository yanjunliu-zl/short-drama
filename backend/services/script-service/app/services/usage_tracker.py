"""AI 用量跟踪 — 上报到 content-service 持久化"""
import logging
import os
import httpx

logger = logging.getLogger(__name__)

USAGE_API = os.getenv("USAGE_API_URL", "http://content-service:8081/api/v1/usage/record")

# DeepSeek 模型定价（每百万 token）
DEEPSEEK_PRICE_PER_1M_IN = 1.0    # RMB
DEEPSEEK_PRICE_PER_1M_OUT = 2.0   # RMB

# Seedance 预估定价（每次调用）
SEEDANCE_IMAGE_PRICE = 0.10   # RMB per image
SEEDANCE_VIDEO_PRICE = 0.50   # RMB per video second (avg 5s → 2.5 RMB)


async def track_llm_usage(user_id: str, model_name: str, tokens_in: int, tokens_out: int,
                          duration_ms: int = 0, endpoint: str = "", service_name: str = ""):
    """跟踪 LLM 调用用量"""
    if not user_id:
        user_id = os.getenv("DEFAULT_USER_ID", "anonymous")
    if not service_name:
        service_name = os.getenv("SERVICE_NAME", "script-service")

    cost = (tokens_in / 1_000_000 * DEEPSEEK_PRICE_PER_1M_IN +
            tokens_out / 1_000_000 * DEEPSEEK_PRICE_PER_1M_OUT)

    payload = {
        "userId": user_id,
        "modelType": "llm",
        "modelName": model_name,
        "tokensIn": tokens_in,
        "tokensOut": tokens_out,
        "callCount": 1,
        "durationMs": duration_ms,
        "endpoint": endpoint,
        "serviceName": service_name,
        "costEstimate": round(cost, 4),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(USAGE_API, json=payload)
    except Exception as e:
        logger.debug(f"用量上报失败（非关键）: {e}")


async def track_image_usage(user_id: str, model_name: str, count: int = 1,
                            duration_ms: int = 0, endpoint: str = "", service_name: str = ""):
    """跟踪图像生成用量"""
    if not user_id:
        user_id = os.getenv("DEFAULT_USER_ID", "anonymous")
    if not service_name:
        service_name = os.getenv("SERVICE_NAME", "llmhua-service")

    payload = {
        "userId": user_id,
        "modelType": "image",
        "modelName": model_name,
        "tokensIn": 0,
        "tokensOut": 0,
        "callCount": count,
        "durationMs": duration_ms,
        "endpoint": endpoint,
        "serviceName": service_name,
        "costEstimate": round(SEEDANCE_IMAGE_PRICE * count, 4),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(USAGE_API, json=payload)
    except Exception as e:
        logger.debug(f"用量上报失败（非关键）: {e}")


async def track_video_usage(user_id: str, model_name: str, count: int = 1,
                            duration_ms: int = 0, endpoint: str = "", service_name: str = ""):
    """跟踪视频生成用量"""
    if not user_id:
        user_id = os.getenv("DEFAULT_USER_ID", "anonymous")
    if not service_name:
        service_name = os.getenv("SERVICE_NAME", "llmhua-service")

    payload = {
        "userId": user_id,
        "modelType": "video",
        "modelName": model_name,
        "tokensIn": 0,
        "tokensOut": 0,
        "callCount": count,
        "durationMs": duration_ms,
        "endpoint": endpoint,
        "serviceName": service_name,
        "costEstimate": round(SEEDANCE_VIDEO_PRICE * 5 * count, 4),  # 平均5秒
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(USAGE_API, json=payload)
    except Exception as e:
        logger.debug(f"用量上报失败（非关键）: {e}")
