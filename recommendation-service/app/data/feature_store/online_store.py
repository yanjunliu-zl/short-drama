"""Online Feature Store — Redis-backed low-latency feature serving.

工业界对标: Feast OnlineStore (Redis/DynamoDB) → 毫秒级特征查询

Features are pre-computed by the stream aggregator (Flink-style)
and stored in Redis for < 5ms retrieval at request time.
"""
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class OnlineFeatureStore:
    """Redis-backed online feature store for real-time serving.

    Key pattern: fs:{domain}:{user_id|item_id}:{feature_name}
    TTL: varies by refresh cadence (realtime=300s, hourly=3600s, daily=86400s)
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client

    @staticmethod
    def _key(domain: str, entity_id: str, feature_name: str) -> str:
        return f"fs:{domain}:{entity_id}:{feature_name}"

    async def get_user_feature(self, user_id: str, feature_name: str) -> Any:
        """Get a single user feature value."""
        if not self.redis:
            return None
        try:
            key = self._key("user", user_id, feature_name)
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    async def get_user_features(self, user_id: str,
                                feature_names: List[str]) -> Dict[str, Any]:
        """Get multiple user features in one pipeline call."""
        if not self.redis or not feature_names:
            return {}

        try:
            pipe = self.redis.pipeline()
            for name in feature_names:
                key = self._key("user", user_id, name)
                pipe.get(key)
            results = await pipe.execute()

            features = {}
            for name, value in zip(feature_names, results):
                if value is not None:
                    try:
                        features[name] = json.loads(value)
                    except json.JSONDecodeError:
                        features[name] = value
            return features
        except Exception as e:
            logger.debug(f"OnlineStore get_user_features failed: {e}")
            return {}

    async def get_item_feature(self, item_id: str, feature_name: str) -> Any:
        """Get a single item feature value."""
        if not self.redis:
            return None
        try:
            key = self._key("item", item_id, feature_name)
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    async def get_item_features(self, item_id: str,
                                feature_names: List[str]) -> Dict[str, Any]:
        """Get multiple item features."""
        if not self.redis or not feature_names:
            return {}
        try:
            pipe = self.redis.pipeline()
            for name in feature_names:
                key = self._key("item", item_id, name)
                pipe.get(key)
            results = await pipe.execute()
            return {
                name: json.loads(val) if val else None
                for name, val in zip(feature_names, results)
            }
        except Exception:
            return {}

    async def set_feature(self, domain: str, entity_id: str,
                          feature_name: str, value: Any,
                          ttl: int = 3600):
        """Set a feature value with TTL."""
        if not self.redis:
            return
        try:
            key = self._key(domain, entity_id, feature_name)
            await self.redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"OnlineStore set failed: {e}")

    async def set_features_batch(self, domain: str, entity_id: str,
                                  features: Dict[str, Any], ttl: int = 3600):
        """Set multiple features in one pipeline."""
        if not self.redis or not features:
            return
        try:
            pipe = self.redis.pipeline()
            for name, value in features.items():
                key = self._key(domain, entity_id, name)
                pipe.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            await pipe.execute()
        except Exception as e:
            logger.debug(f"OnlineStore batch set failed: {e}")
