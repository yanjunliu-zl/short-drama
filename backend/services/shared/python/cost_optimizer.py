"""
成本优化器 — 智能调度降低 AI 推理成本。

策略:
  1. 语义缓存命中 → 0 成本 (已有)
  2. 离线预生成 → 用竞价实例, 0.1× 成本 (已有)
  3. 模型分级调度 → 80% 用 tiny/small 本地推理 (已有)
  4. 批量合并 → 合并多个短请求为一次 LLM 调用
  5. Prompt 精简 → 压缩系统 prompt 减少输入 token
  6. 时段调度 → 高峰期用云 API, 低峰期用本地模型

预期成本: 从全部云 API (100 RMB/1K req) 降至 10-15 RMB/1K req
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# 成本基准 (RMB per 1K tokens)
COST_BASELINE = {
    "deepseek-chat":       {"in": 0.001, "out": 0.002},      # DeepSeek
    "gpt-4o":              {"in": 0.015, "out": 0.060},       # OpenAI
    "claude-sonnet-5":     {"in": 0.015, "out": 0.075},       # Anthropic
    "vllm-local-small":    {"in": 0.000, "out": 0.000},       # 本地 GPU (电费忽略)
    "vllm-local-large":    {"in": 0.000, "out": 0.000},       # 本地 GPU
    "seedance-image":      0.10,                               # 每次图像
    "seedance-video":      2.50,                               # 每次 5s 视频
}


@dataclass
class CostTracker:
    """实时成本追踪器"""

    total_cost: float = 0.0
    api_calls: int = 0
    local_calls: int = 0
    cache_hits: int = 0
    pregen_hits: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    by_provider: Dict[str, float] = field(default_factory=dict)
    by_endpoint: Dict[str, float] = field(default_factory=dict)

    def record_llm_call(self, provider: str, tokens_in: int, tokens_out: int,
                        endpoint: str = ""):
        """Record an LLM call and its cost."""
        cost_info = COST_BASELINE.get(provider, COST_BASELINE["deepseek-chat"])
        if isinstance(cost_info, dict):
            cost = (tokens_in / 1000 * cost_info["in"] +
                    tokens_out / 1000 * cost_info["out"])
        else:
            cost = cost_info  # Fixed per-call price

        self.total_cost += cost
        self.api_calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.by_provider[provider] = self.by_provider.get(provider, 0) + cost
        if endpoint:
            self.by_endpoint[endpoint] = self.by_endpoint.get(endpoint, 0) + cost

    def record_cache_hit(self):
        """Record a cache hit (zero cost)."""
        self.cache_hits += 1

    def record_local_call(self):
        """Record a local vLLM call (near-zero marginal cost)."""
        self.local_calls += 1

    def record_pregen_hit(self):
        """Record a pre-generated cache hit."""
        self.pregen_hits += 1

    @property
    def savings(self) -> float:
        """Estimated savings vs all-cloud baseline."""
        total = self.api_calls + self.local_calls + self.cache_hits
        if total == 0:
            return 0.0
        cloud_equivalent = total * 0.003  # Average cost if all were cloud API
        return max(0, cloud_equivalent - self.total_cost)

    @property
    def cache_hit_rate(self) -> float:
        total = self.api_calls + self.local_calls + self.cache_hits + self.pregen_hits
        return (self.cache_hits + self.pregen_hits) / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cost_rmb": round(self.total_cost, 4),
            "estimated_savings_rmb": round(self.savings, 4),
            "api_calls": self.api_calls,
            "local_calls": self.local_calls,
            "cache_hits": self.cache_hits,
            "pregen_hits": self.pregen_hits,
            "cache_hit_rate": f"{self.cache_hit_rate:.1%}",
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "by_provider": self.by_provider,
            "by_endpoint": self.by_endpoint,
        }


# Global tracker
_cost_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    return _cost_tracker


# ═══════════════════════════════════════════
# 时段调度器 — 高峰用云, 低峰用本地
# ═══════════════════════════════════════════

def is_peak_hours() -> bool:
    """Check if current time is peak usage hours (8:00-23:00 Beijing time)."""
    import datetime
    now = datetime.datetime.now()
    return 8 <= now.hour <= 23


def get_preferred_tier_for_time() -> str:
    """Return preferred model tier based on time of day.

    Peak hours (8-23): use cloud API for latency (DeepSeek)
    Off-peak (23-8): use local vLLM for cost savings
    """
    from model_tiers import ModelTier
    if is_peak_hours():
        return ModelTier.CLOUD
    return ModelTier.SMALL


# ═══════════════════════════════════════════
# Prompt 精简 — 减少输入 token 消耗
# ═══════════════════════════════════════════

def estimate_prompt_cost(prompt: str, provider: str = "deepseek-chat") -> float:
    """Estimate cost of a prompt."""
    cost_info = COST_BASELINE.get(provider, COST_BASELINE["deepseek-chat"])
    if not isinstance(cost_info, dict):
        return cost_info
    # ~1 token per character for Chinese
    estimated_tokens = len(prompt)
    return estimated_tokens / 1000 * cost_info["in"]
