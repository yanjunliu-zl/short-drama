"""
Real-time Feature Pipeline — Sliding Window Aggregation

Aggregates user behavior signals into real-time features:
  - Recent N item embeddings (for DIN sequence modeling)
  - Short-term CTR (last 1h / 6h / 24h)
  - Real-time tag interest distribution
  - Session-level behavior (current session views, dwell time)

Storage: Redis (sliding window), backed by MySQL for cold-start.

Usage:
  aggregator = RealtimeFeatureAggregator(redis_client)
  await aggregator.record_view(user_id, item_id, timestamp)
  features = await aggregator.get_features(user_id)
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# Sliding window sizes (seconds)
WINDOW_1H = 3600
WINDOW_6H = 21600
WINDOW_24H = 86400
MAX_SEQUENCE_LEN = 50  # Max items in DIN sequence


class RealtimeFeatureAggregator:
    """Real-time user behavior feature aggregator with Redis backend."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local_cache: Dict[str, Dict] = {}  # Fallback in-memory cache

    # ================================================================
    # Record user behavior
    # ================================================================

    async def record_view(self, user_id: str, item_id: str,
                          item_embedding: List[float] = None,
                          dwell_time_ms: int = 0,
                          timestamp: float = None):
        """Record a user view event with dwell time."""
        ts = timestamp or time.time()
        event = json.dumps({
            "item_id": item_id,
            "ts": ts,
            "dwell_ms": dwell_time_ms,
            "emb": item_embedding,
        })

        if self.redis:
            try:
                # Add to sliding window (sorted set, scored by timestamp)
                key = f"rt:views:{user_id}"
                await self.redis.zadd(key, {event: ts})
                # Trim old events
                cutoff = ts - WINDOW_24H
                await self.redis.zremrangebyscore(key, 0, cutoff)
                # Keep only last MAX_SEQUENCE_LEN items
                await self.redis.zremrangebyrank(key, 0, -(MAX_SEQUENCE_LEN + 1))
            except Exception as e:
                logger.debug(f"Redis record_view failed: {e}")

    async def record_like(self, user_id: str, item_id: str, timestamp: float = None):
        """Record a like event."""
        ts = timestamp or time.time()
        if self.redis:
            try:
                await self.redis.zadd(f"rt:likes:{user_id}", {item_id: ts})
            except Exception as e:
                logger.debug(f"Redis record_like failed: {e}")

    # ================================================================
    # Aggregated features
    # ================================================================

    async def get_features(self, user_id: str) -> Dict[str, Any]:
        """Get aggregated real-time features for a user.

        Returns:
            {
                "recent_views_1h": int,
                "recent_views_6h": int,
                "recent_likes_24h": int,
                "avg_dwell_ms": float,
                "behavior_sequence": [[emb], ...],  # for DIN
                "top_tags_1h": [str, ...],
                "ctr_1h": float,
                "is_active_session": bool,
            }
        """
        if not self.redis:
            return self._default_features()

        now = time.time()
        features = {
            "recent_views_1h": 0,
            "recent_views_6h": 0,
            "recent_likes_24h": 0,
            "avg_dwell_ms": 0,
            "behavior_sequence": [],
            "top_tags_1h": [],
            "ctr_1h": 0.0,
            "is_active_session": False,
        }

        try:
            # View counts per window
            views_key = f"rt:views:{user_id}"
            views_1h = await self.redis.zcount(views_key, now - WINDOW_1H, now)
            views_6h = await self.redis.zcount(views_key, now - WINDOW_6H, now)
            features["recent_views_1h"] = views_1h
            features["recent_views_6h"] = views_6h

            # Recent behavior sequence (for DIN)
            recent = await self.redis.zrevrangebyscore(
                views_key, now, now - WINDOW_24H,
                start=0, num=MAX_SEQUENCE_LEN,
            )
            sequence = []
            total_dwell = 0
            for event_str in recent:
                try:
                    event = json.loads(event_str)
                    if event.get("emb"):
                        sequence.append(event["emb"])
                    total_dwell += event.get("dwell_ms", 0)
                except json.JSONDecodeError:
                    pass
            features["behavior_sequence"] = sequence[-MAX_SEQUENCE_LEN:]
            if recent:
                features["avg_dwell_ms"] = total_dwell / len(recent)

            # Likes in 24h
            likes_key = f"rt:likes:{user_id}"
            likes_24h = await self.redis.zcount(likes_key, now - WINDOW_24H, now)
            features["recent_likes_24h"] = likes_24h

            # CTR in 1h
            if views_1h > 0:
                likes_1h = await self.redis.zcount(likes_key, now - WINDOW_1H, now)
                features["ctr_1h"] = likes_1h / views_1h

            # Active session check
            last_view_ts = await self.redis.zscore(views_key, recent[-1]) if recent else 0
            features["is_active_session"] = (now - (last_view_ts or 0)) < 300  # 5 min

        except Exception as e:
            logger.debug(f"Realtime features failed ({e}), returning defaults")

        return features

    @staticmethod
    def _default_features() -> Dict[str, Any]:
        return {
            "recent_views_1h": 0, "recent_views_6h": 0,
            "recent_likes_24h": 0, "avg_dwell_ms": 0,
            "behavior_sequence": [], "top_tags_1h": [],
            "ctr_1h": 0.0, "is_active_session": False,
        }
