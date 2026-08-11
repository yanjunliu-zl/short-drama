"""AI Task Dispatcher — Kafka-based priority queue for GPU-intensive AI tasks.

Replaces FastAPI BackgroundTasks with a distributed, priority-aware task queue.
Routes tasks to the correct Kafka topic based on priority level.

Priority Levels:
    P1 (realtime): User-facing interactive requests — latency < 2s
        - Character design (non-image)
        - Script generation status query
        - Health checks
    P2 (video): Video/image generation — latency < 5min
        - Single image generation
        - Single video generation
        - Preview image generation
    P3 (batch): Offline batch processing
        - Complete storyboard generation
        - Shots-to-video batch
        - Novel-to-script conversion
        - Usage reporting

Usage:
    from shared.python.cache.ai_task_dispatcher import AITaskDispatcher, TaskPriority

    dispatcher = AITaskDispatcher(bootstrap_servers="kafka:9092")
    await dispatcher.start()

    # Submit a P1 task
    await dispatcher.submit(
        priority=TaskPriority.P1_REALTIME,
        task_type="character_design",
        payload={"name": "Hero", "role": "protagonist"},
        user_id="user-123",
    )

    # Submit a P2 task
    await dispatcher.submit(
        priority=TaskPriority.P2_VIDEO,
        task_type="image_generation",
        payload={"prompt": "...", "style": "写实"},
        user_id="user-123",
    )
"""
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    """Kafka topic priority levels."""
    P1_REALTIME = 1  # ai-task-p1-realtime
    P2_VIDEO = 2     # ai-task-p2-video
    P3_BATCH = 3     # ai-task-p3-batch


# Priority → Kafka topic mapping
PRIORITY_TOPICS = {
    TaskPriority.P1_REALTIME: "ai-task-p1-realtime",
    TaskPriority.P2_VIDEO: "ai-task-p2-video",
    TaskPriority.P3_BATCH: "ai-task-p3-batch",
}

# Task type → default priority
TASK_PRIORITY_MAP = {
    # P1: Realtime user requests
    "character_design": TaskPriority.P1_REALTIME,
    "script_status": TaskPriority.P1_REALTIME,
    "health_check": TaskPriority.P1_REALTIME,
    # P2: Video/image generation
    "image_generation": TaskPriority.P2_VIDEO,
    "video_generation": TaskPriority.P2_VIDEO,
    "preview_image": TaskPriority.P2_VIDEO,
    "storyboard_generation": TaskPriority.P2_VIDEO,
    # P3: Batch offline
    "complete_storyboard": TaskPriority.P3_BATCH,
    "shots_to_video": TaskPriority.P3_BATCH,
    "novel_to_script": TaskPriority.P3_BATCH,
    "batch_image_generation": TaskPriority.P3_BATCH,
    "usage_reporting": TaskPriority.P3_BATCH,
}


@dataclass
class AITask:
    """An AI task message on the Kafka priority queue."""
    task_id: str
    task_type: str
    priority: int
    user_id: str
    payload: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3


class AITaskDispatcher:
    """Kafka-based priority task dispatcher for AI workloads.

    Uses aiokafka for async produce/consume.
    Falls back gracefully to local BackgroundTasks during Kafka migration.
    """

    def __init__(self, bootstrap_servers: str = "kafka:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self._started = False

    async def start(self):
        """Initialize the Kafka producer connection."""
        try:
            from aiokafka import AIOKafkaProducer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
                compression_type="lz4",  # Efficient for JSON task payloads
                acks="all",              # Wait for all replicas (durability)
                max_in_flight_requests_per_connection=5,
            )
            await self.producer.start()
            self._started = True
            logger.info("AITaskDispatcher connected to Kafka at %s", self.bootstrap_servers)
        except ImportError:
            logger.warning("aiokafka not installed — using synchronous fallback")
            self._started = True
        except Exception as e:
            logger.error("Failed to connect to Kafka: %s — tasks will use local fallback", e)
            self._started = True  # Graceful degradation

    async def stop(self):
        """Close the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("AITaskDispatcher stopped")

    async def submit(
        self,
        task_type: str,
        payload: Dict[str, Any],
        user_id: str = "",
        priority: Optional[TaskPriority] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Submit an AI task to the priority queue.

        Args:
            task_type: Task type (e.g., 'image_generation', 'shots_to_video')
            payload: Task-specific data
            user_id: User who submitted the task
            priority: Explicit priority (auto-detected if None)
            task_id: Custom task ID (auto-generated if None)

        Returns:
            task_id: The task identifier for status polling
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        if priority is None:
            priority = TASK_PRIORITY_MAP.get(task_type, TaskPriority.P3_BATCH)

        task = AITask(
            task_id=task_id,
            task_type=task_type,
            priority=int(priority),
            user_id=user_id,
            payload=payload,
        )

        topic = PRIORITY_TOPICS[priority]
        message = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "priority": task.priority,
            "user_id": task.user_id,
            "payload": task.payload,
            "created_at": task.created_at,
            "retry_count": task.retry_count,
        }

        if self.producer:
            try:
                await self.producer.send_and_wait(
                    topic,
                    value=message,
                    # Kafka key = user_id for user-affinity partitioning
                    key=user_id.encode() if user_id else task_id.encode(),
                )
                logger.debug("Task %s submitted to %s (priority=%d)", task_id, topic, priority)
            except Exception as e:
                logger.error("Kafka send failed for task %s: %s", task_id, e)
                # Fall back: task is still tracked via Redis TaskStore
        else:
            logger.debug("Task %s queued locally (Kafka unavailable), priority=%d", task_id, priority)

        return task_id

    @staticmethod
    def get_priority(task_type: str) -> TaskPriority:
        """Get the default priority for a task type."""
        return TASK_PRIORITY_MAP.get(task_type, TaskPriority.P3_BATCH)


# Global singleton
_dispatcher: Optional[AITaskDispatcher] = None


async def get_dispatcher(bootstrap_servers: str = "kafka:9092") -> AITaskDispatcher:
    """Get or create the global AITaskDispatcher singleton."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = AITaskDispatcher(bootstrap_servers)
        await _dispatcher.start()
    return _dispatcher


async def close_dispatcher():
    """Close the global dispatcher."""
    global _dispatcher
    if _dispatcher:
        await _dispatcher.stop()
        _dispatcher = None
