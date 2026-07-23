"""Kafka Event Producer — 用户行为事件实时写入 Kafka。

工业界对标: 字节跳动 BehaviorLog → Kafka → Flink → Feature Store

事件类型:
  - impression: 内容曝光 (曝光时刻, 位置, recall_source)
  - click: 点击 (点击时间, 停留时长)
  - like: 点赞
  - share: 分享
  - complete: 完播

分区策略: user_id hash → 同一用户事件进同一分区 (保证时序)
"""
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    IMPRESSION = "impression"
    CLICK = "click"
    LIKE = "like"
    SHARE = "share"
    COMPLETE = "complete"
    SKIP = "skip"


@dataclass
class UserEvent:
    """Standardized user behavior event — same schema as ClickHouse user_events."""
    event_type: str              # impression / click / like / share / complete / skip
    user_id: str
    item_id: str
    event_time: float = 0.0      # Unix timestamp (seconds)
    recall_source: str = ""      # cf / content / hot / author / search / embedding
    position: int = 0            # Position in recommendation list
    dwell_ms: int = 0            # Dwell time (click→exit)
    session_id: str = ""         # Session identifier
    scene: str = "recommend"     # recommend / search / detail
    metadata: dict = None        # Extensible JSON payload

    def __post_init__(self):
        if not self.event_time:
            self.event_time = time.time()
        if self.metadata is None:
            self.metadata = {}


class EventProducer:
    """Kafka-backed user event producer.

    Production: aiokafka producer to Kafka cluster
    Development: writes to Redis list + ClickHouse insert
    """

    def __init__(self, kafka_brokers: str = "",
                 redis_client=None,
                 clickhouse_client=None):
        self.kafka_brokers = kafka_brokers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
        self.redis = redis_client
        self.clickhouse = clickhouse_client
        self._producer = None
        self._use_kafka = bool(self.kafka_brokers)

    async def _init_kafka(self):
        if self._producer is not None:
            return
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_brokers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
                compression_type="gzip",
                linger_ms=10,         # Batch 10ms of events
                batch_size=32768,     # 32KB batches
            )
            await self._producer.start()
            logger.info(f"Kafka producer connected: {self.kafka_brokers}")
        except ImportError:
            logger.info("aiokafka not installed — using Redis+ClickHouse fallback")
        except Exception as e:
            logger.warning(f"Kafka init failed ({e}) — using fallback")

    async def send(self, event: UserEvent):
        """Send event to Kafka topic: user-events (partitioned by user_id)."""
        if self._use_kafka:
            await self._init_kafka()
            if self._producer:
                try:
                    await self._producer.send_and_wait(
                        "user-events",
                        key=event.user_id.encode(),
                        value=asdict(event),
                    )
                    return
                except Exception as e:
                    logger.debug(f"Kafka send failed ({e}) — falling back")

        # Fallback: Redis list + ClickHouse
        await self._send_fallback(event)

    async def _send_fallback(self, event: UserEvent):
        """Fallback: Redis list (recent) + ClickHouse (permanent)."""
        # Redis: keep last 1000 events per user for real-time features
        if self.redis:
            try:
                key = f"stream:events:{event.user_id}"
                await self.redis.lpush(key, json.dumps(asdict(event), ensure_ascii=False))
                await self.redis.ltrim(key, 0, 999)
                await self.redis.expire(key, 86400)
            except Exception:
                pass

        # ClickHouse: permanent storage for offline analytics
        if self.clickhouse:
            try:
                await self.clickhouse.insert_event(
                    event_type=event.event_type,
                    user_id=event.user_id,
                    item_id=event.item_id,
                    recall_source=event.recall_source,
                    position=event.position,
                    dwell_ms=event.dwell_ms,
                    session_id=event.session_id,
                    metadata=event.metadata,
                )
            except Exception:
                pass

    async def close(self):
        if self._producer:
            await self._producer.stop()
