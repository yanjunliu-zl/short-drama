"""
3 级模型调度器 — 蒸馏+量化的推理优化。

Tier 1 (Tiny):   Qwen2.5-1.5B-Instruct int4  — 简单剧本生成, 0.5s 延迟, 3GB VRAM
Tier 2 (Small):  Qwen2.5-7B-Instruct int4    — 中等剧本, 1s 延迟, 6GB VRAM
Tier 3 (Large):  Qwen2.5-14B-Instruct        — 复杂长篇, 2s 延迟, 28GB VRAM
Tier 4 (Cloud):  DeepSeek / GPT-4o           — 最复杂任务, API 调用

路由策略:
  - 短篇 (≤5集) → Tier 1 或 2
  - 中篇 (5-8集) → Tier 2 或 3
  - 长篇 (>8集) → Tier 3 或 Cloud
  - 大纲扩展 → Tier 1 (结构简单)
  - 小说改编 → Tier 3 或 Cloud (需要理解长上下文)
  - 质量评审 → Tier 2 (简单打分任务)

成本节省: 80% 请求用 Tier 1/2 (免费本地推理), 20% 用 Cloud API
"""
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class ModelTier:
    TINY = "tiny"      # 1.5B int4
    SMALL = "small"    # 7B int4
    LARGE = "large"    # 14B
    CLOUD = "cloud"    # API


def route_by_task(request: dict) -> str:
    """Route request to the appropriate model tier based on complexity.

    Heuristics:
      - Short script + outline → tiny
      - Medium script or simple novel → small
      - Long script or complex novel → large
      - Very long novel → cloud
    """
    length = request.get("length", "短篇")
    has_novel = bool(request.get("novel_content", ""))
    novel_len = len(request.get("novel_content", ""))
    has_outline = bool(request.get("outline", ""))

    # Simple outline expansion → tiny
    if has_outline and not has_novel and length == "短篇":
        return ModelTier.TINY

    # Short novel adaptation → small
    if has_novel and novel_len < 50000:
        return ModelTier.SMALL

    # Medium complexity → small/large
    if length in ("中篇",):
        return ModelTier.SMALL

    # Long or complex novel → large
    if length == "长篇" or novel_len > 50000:
        return ModelTier.LARGE

    # Very long novel → cloud for quality
    if novel_len > 200000:
        return ModelTier.CLOUD

    return ModelTier.SMALL  # Default


# Quantization presets for vLLM
QUANT_CONFIGS = {
    "awq": {
        "quantization": "awq",
        "description": "AWQ 4-bit — best accuracy/speed trade-off"
    },
    "gptq": {
        "quantization": "gptq",
        "description": "GPTQ 4-bit — widely compatible"
    },
    "int8": {
        "quantization": None,  # vLLM doesn't need explicit int8
        "description": "INT8 — vLLM default, best accuracy"
    },
    "fp16": {
        "quantization": None,
        "dtype": "float16",
        "description": "FP16 — maximum accuracy for large models"
    },
}

# Model specifications per tier
TIER_MODELS = {
    ModelTier.TINY: {
        "model": "Qwen/Qwen2.5-1.5B-Instruct",
        "quantization": "awq",
        "max_model_len": 4096,
        "gpu_memory": 0.85,
        "tensor_parallel": 1,
        "vram_required": "3GB",
        "latency_ms": 500,
    },
    ModelTier.SMALL: {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "quantization": "awq",
        "max_model_len": 8192,
        "gpu_memory": 0.85,
        "tensor_parallel": 1,
        "vram_required": "6GB",
        "latency_ms": 1000,
    },
    ModelTier.LARGE: {
        "model": "Qwen/Qwen2.5-14B-Instruct",
        "quantization": None,
        "max_model_len": 16384,
        "gpu_memory": 0.90,
        "tensor_parallel": 2,
        "vram_required": "28GB",
        "latency_ms": 2000,
    },
}


def get_vllm_args(tier: str) -> list:
    """Generate vLLM CLI arguments for a given model tier."""
    spec = TIER_MODELS.get(tier, TIER_MODELS[ModelTier.SMALL])
    args = [
        "--model", spec["model"],
        "--max-model-len", str(spec["max_model_len"]),
        "--gpu-memory-utilization", str(spec["gpu_memory"]),
        "--tensor-parallel-size", str(spec["tensor_parallel"]),
    ]
    if spec.get("quantization"):
        args.extend(["--quantization", spec["quantization"]])
    return args
