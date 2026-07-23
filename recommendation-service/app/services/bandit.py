"""
LinUCB Contextual Bandit — 推荐策略在线学习

每个用户维护独立的线性模型，根据交互反馈动态调整各推荐来源的权重。
"""
import json
import logging
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Action space: the 5 recall source channels we optimize weights for ──
RECALL_SOURCES = ["cf", "content", "hot", "author", "search"]

# ── Context features (user-item interaction dimensions) ──
CONTEXT_DIM = 8  # tag_match, genre_match, author_match, item_age, time_of_day, like_density, user_activity, is_new_user

# ── Hyperparameters ──
ALPHA = 1.0       # exploration bonus (higher = more exploration)
LAMBDA = 0.1      # L2 regularization for linear model
DISCOUNT = 0.995  # decay factor for older rewards


def _build_context(item_features: Dict, user_features: Dict) -> np.ndarray:
    """Build context vector from item and user features."""
    ctx = np.zeros(CONTEXT_DIM, dtype=np.float32)
    ctx[0] = min(float(item_features.get("tag_match_count", 0)) / 5.0, 1.0)
    ctx[1] = float(item_features.get("genre_match", 0))
    ctx[2] = float(item_features.get("author_match", 0))
    ctx[3] = min(float(item_features.get("item_age_days", 0)) / 365.0, 1.0)
    ctx[4] = float(item_features.get("hour_of_day", 12)) / 24.0
    ctx[5] = min(float(item_features.get("item_like_count", 0)) / 1000.0, 1.0)
    ctx[6] = min(float(user_features.get("total_interactions", 0)) / 100.0, 1.0)
    ctx[7] = 1.0 if user_features.get("is_new_user", True) else 0.0
    return ctx


class LinUCBModel:
    """Per-user LinUCB model — one linear regressor per recall source."""

    def __init__(self, alpha: float = ALPHA, lambda_: float = LAMBDA):
        self.alpha = alpha
        self.lambda_ = lambda_
        # A[a] = covariance matrix (d x d), b[a] = reward-weighted features (d,)
        self.A: Dict[str, np.ndarray] = {}
        self.b: Dict[str, np.ndarray] = {}
        self.theta: Dict[str, np.ndarray] = {}  # cached linear weights
        self._init_arms()

    def _init_arms(self):
        d = CONTEXT_DIM
        I = np.eye(d, dtype=np.float32) * self.lambda_
        for src in RECALL_SOURCES:
            self.A[src] = I.copy()
            self.b[src] = np.zeros(d, dtype=np.float32)
            self.theta[src] = np.zeros(d, dtype=np.float32)

    def get_action_weights(self, context: np.ndarray) -> Dict[str, float]:
        """Compute UCB scores for each recall source given the context."""
        scores = {}
        for src in RECALL_SOURCES:
            A_inv = np.linalg.inv(self.A[src])
            theta = A_inv @ self.b[src]
            self.theta[src] = theta
            # UCB = predicted reward + exploration bonus
            predicted = float(theta @ context)
            bonus = self.alpha * math.sqrt(float(context @ A_inv @ context) + 1e-8)
            scores[src] = predicted + bonus
        # Normalize to [0, 1] range
        min_s = min(scores.values())
        max_s = max(scores.values()) + 1e-8
        return {k: (v - min_s) / (max_s - min_s + 1e-8) for k, v in scores.items()}

    def update(self, source: str, context: np.ndarray, reward: float):
        """Update the model for a specific recall source with observed reward."""
        if source not in self.A:
            return
        # Apply discount to existing model
        self.A[source] = self.A[source] * DISCOUNT + np.eye(CONTEXT_DIM) * self.lambda_ * (1 - DISCOUNT)
        self.b[source] = self.b[source] * DISCOUNT
        # Update with new observation
        ctx = context.reshape(-1, 1)
        self.A[source] += ctx @ ctx.T
        self.b[source] += (ctx * reward).flatten()
        # Invalidate cached theta
        self.theta.pop(source, None)

    def to_dict(self) -> dict:
        return {
            "A": {k: v.tolist() for k, v in self.A.items()},
            "b": {k: v.tolist() for k, v in self.b.items()},
        }

    @classmethod
    def from_dict(cls, data: dict, alpha: float = ALPHA, lambda_: float = LAMBDA) -> "LinUCBModel":
        model = cls(alpha=alpha, lambda_=lambda_)
        for src in RECALL_SOURCES:
            if src in data.get("A", {}):
                model.A[src] = np.array(data["A"][src], dtype=np.float32)
            if src in data.get("b", {}):
                model.b[src] = np.array(data["b"][src], dtype=np.float32)
        return model


class BanditService:
    """Manages per-user bandit models, persisted in Redis."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._cache: Dict[str, LinUCBModel] = {}  # in-memory cache

    async def get_model(self, user_id: str) -> LinUCBModel:
        if user_id in self._cache:
            return self._cache[user_id]
        # Try Redis
        if self.redis:
            try:
                raw = await self.redis.get(f"bandit:model:{user_id}")
                if raw:
                    data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                    model = LinUCBModel.from_dict(data)
                    self._cache[user_id] = model
                    return model
            except Exception:
                pass
        model = LinUCBModel()
        self._cache[user_id] = model
        return model

    async def save_model(self, user_id: str, model: LinUCBModel):
        self._cache[user_id] = model
        if self.redis:
            try:
                await self.redis.setex(
                    f"bandit:model:{user_id}",
                    86400 * 7,  # 7-day TTL
                    json.dumps(model.to_dict()),
                )
            except Exception as e:
                logger.debug("Bandit model save to Redis failed: %s", e)

    async def record_feedback(self, user_id: str, case_id: str, action: str,
                               recall_source: str, item_features: Dict, user_features: Dict):
        """Record user interaction and update the bandit model."""
        model = await self.get_model(user_id)
        context = _build_context(item_features, user_features)
        # Reward mapping
        rewards = {"view": 1.0, "like": 3.0, "share": 5.0, "skip": -0.5}
        reward = rewards.get(action, 0.0)
        model.update(recall_source, context, reward)
        await self.save_model(user_id, model)
        logger.debug("Bandit feedback: user=%s action=%s source=%s reward=%.1f", user_id, action, recall_source, reward)

    async def get_source_weights(self, user_id: str, item_features: Dict, user_features: Dict) -> Dict[str, float]:
        """Get bandit-predicted weights for each recall source."""
        model = await self.get_model(user_id)
        context = _build_context(item_features, user_features)
        return model.get_action_weights(context)


# ── Singleton ──
_bandit_service: Optional[BanditService] = None


def get_bandit_service(redis_client=None) -> BanditService:
    global _bandit_service
    if _bandit_service is None:
        _bandit_service = BanditService(redis_client=redis_client)
    return _bandit_service
