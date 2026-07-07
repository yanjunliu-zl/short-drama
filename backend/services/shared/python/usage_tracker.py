"""AI 用量跟踪 — 上报到 content-service 持久化。

支持从 LangChain LLM response 中提取真实 token 用量（优先），
无法提取时回退到字符数估算。
"""
import logging
import os
import re
from typing import Any, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

USAGE_API = os.getenv("USAGE_API_URL", "http://content-service:8081/api/v1/usage/record")

# Provider 定价（每百万 token / 每次调用）
PRICING = {
    "deepseek": {"in": 1.0, "out": 2.0},       # RMB / 1M tokens
    "openai":   {"in": 15.0, "out": 60.0},      # gpt-4o approximate
    "anthropic":{"in": 15.0, "out": 75.0},       # claude-sonnet-5 approximate
    "seedance_image": 0.10,                      # RMB per image
    "seedance_video": 2.50,                      # RMB per video (avg 5s)
}


def extract_real_usage(response: Any) -> Tuple[int, int]:
    """Extract real (prompt_tokens, completion_tokens) from LangChain LLM response.

    LangChain's AIMessage stores usage in response_metadata.token_usage
    with prompt_tokens and completion_tokens fields.

    Args:
        response: An AIMessage returned by llm.ainvoke().

    Returns:
        (prompt_tokens, completion_tokens) — (0, 0) if unavailable.
    """
    try:
        meta = getattr(response, 'response_metadata', {}) or {}
        usage = meta.get('token_usage', {}) or {}
        prompt = int(usage.get('prompt_tokens', 0))
        completion = int(usage.get('completion_tokens', 0))
        if prompt > 0 or completion > 0:
            return prompt, completion
    except Exception:
        pass

    # Try additional_metadata as fallback (some LangChain versions)
    try:
        meta2 = getattr(response, 'additional_kwargs', {}) or {}
        usage2 = meta2.get('token_usage', {}) or {}
        prompt = int(usage2.get('prompt_tokens', 0))
        completion = int(usage2.get('completion_tokens', 0))
        if prompt > 0 or completion > 0:
            return prompt, completion
    except Exception:
        pass

    return 0, 0


def get_pricing_for_model(model_name: str) -> Tuple[float, float]:
    """Get (input_price_per_1M, output_price_per_1M) for a model.

    Returns (DEEPSEEK default, DEEPSEEK default) if model unknown.
    """
    model_lower = model_name.lower()
    if "deepseek" in model_lower:
        return PRICING["deepseek"]["in"], PRICING["deepseek"]["out"]
    if "gpt" in model_lower or "openai" in model_lower:
        return PRICING["openai"]["in"], PRICING["openai"]["out"]
    if "claude" in model_lower or "anthropic" in model_lower:
        return PRICING["anthropic"]["in"], PRICING["anthropic"]["out"]
    return PRICING["deepseek"]["in"], PRICING["deepseek"]["out"]


def estimate_tokens(text: str) -> int:
    """Estimate token count from text.
    Chinese: ~1 char ≈ 1.5 tokens. English: ~1 char ≈ 0.25 tokens.
    Returns a reasonable estimate for mixed Chinese/English text.
    """
    if not text:
        return 0
    # Count Chinese characters (CJK range)
    cjk = len(re.findall(r'[一-鿿㐀-䶿豈-﫿]', text))
    other = len(text) - cjk
    # Chinese ≈ 1.5 tokens/char, other ≈ 0.3 tokens/char
    return int(cjk * 1.5 + other * 0.3)


async def track_llm_usage(
    user_id: str,
    model_name: str = "deepseek-chat",
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
    endpoint: str = "",
    service_name: str = "",
    call_count: int = 1,
    response: Any = None,  # Optional: LangChain AIMessage for real token extraction
):
    """跟踪 LLM 调用用量。

    If `response` is provided, real token counts are extracted from
    response.response_metadata.token_usage (available from DeepSeek, OpenAI, Anthropic).
    Falls back to the `tokens_in`/`tokens_out` estimates if extraction fails.

    Pricing is auto-detected from model_name.
    """
    if not user_id:
        user_id = os.getenv("DEFAULT_USER_ID", "anonymous")
    if not service_name:
        service_name = os.getenv("SERVICE_NAME", "script-service")

    # Try to get real usage from response
    real_in, real_out = 0, 0
    if response is not None:
        real_in, real_out = extract_real_usage(response)

    final_in = real_in if real_in > 0 else tokens_in
    final_out = real_out if real_out > 0 else tokens_out

    price_in, price_out = get_pricing_for_model(model_name)
    cost = (final_in / 1_000_000 * price_in +
            final_out / 1_000_000 * price_out)

    payload = {
        "userId": user_id,
        "modelType": "llm",
        "modelName": model_name,
        "tokensIn": final_in,
        "tokensOut": final_out,
        "estimatedInput": tokens_in,   # Keep estimate for comparison
        "estimatedOutput": tokens_out,
        "callCount": call_count,
        "durationMs": duration_ms,
        "endpoint": endpoint,
        "serviceName": service_name,
        "costEstimate": round(cost, 6),
    }

    # Emit Prometheus metrics
    try:
        from app.middleware.prometheus import script_generation_tokens, script_generation_cost
        script_generation_tokens.labels(token_type='input', service=service_name).inc(final_in)
        script_generation_tokens.labels(token_type='output', service=service_name).inc(final_out)
        script_generation_cost.labels(service=service_name).inc(cost)
    except Exception:
        pass

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
