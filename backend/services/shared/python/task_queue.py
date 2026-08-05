"""
异步任务队列抽象层 — 支持内存队列 (开发) 和 Kafka (生产)。

用途：AI 生成请求异步化，削峰填谷。
  1. 用户提交 AI 请求 → 入队
  2. 立即返回 task_id
  3. Worker 从队列消费 → 执行生成
  4. SSE/Webhook 推送结果

后端切换：设置 TASK_QUEUE_BACKEND=kafka 即切换到 Kafka，
无需修改业务代码。
"""
import asyncio
import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = "default"
    payload: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "queue_name": self.queue_name,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "duration_ms": int(((self.completed_at or time.time()) - self.created_at) * 1000),
        }


class TaskQueueBackend(ABC):
    """Abstract task queue backend."""

    @abstractmethod
    async def enqueue(self, task: Task) -> str:
        """Enqueue a task, return task_id."""

    @abstractmethod
    async def dequeue(self, queue_name: str, timeout: float = 1.0) -> Optional[Task]:
        """Dequeue a task, blocking up to timeout seconds."""

    @abstractmethod
    async def ack(self, task: Task):
        """Acknowledge successful processing."""

    @abstractmethod
    async def nack(self, task: Task, error: str = ""):
        """Negative acknowledge (processing failed)."""

    @abstractmethod
    async def length(self, queue_name: str) -> int:
        """Return current queue depth."""


class MemoryQueue(TaskQueueBackend):
    """In-memory queue (dev/single-node)."""

    def __init__(self, max_size: int = 10000):
        self._queues: Dict[str, deque] = {}
        self._max_size = max_size
        self._results: Dict[str, Task] = {}
        self._events: Dict[str, asyncio.Event] = {}

    def _get_queue(self, name: str) -> deque:
        if name not in self._queues:
            self._queues[name] = deque(maxlen=self._max_size)
        return self._queues[name]

    async def enqueue(self, task: Task) -> str:
        self._results[task.task_id] = task
        self._get_queue(task.queue_name).append(task)
        # Notify any waiting dequeuer
        for event in self._events.values():
            event.set()
        return task.task_id

    async def dequeue(self, queue_name: str, timeout: float = 1.0) -> Optional[Task]:
        q = self._get_queue(queue_name)
        event = self._events.setdefault(queue_name, asyncio.Event())
        if not q:
            event.clear()
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
        return q.popleft() if q else None

    async def ack(self, task: Task):
        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()
        if task.task_id in self._results:
            self._results[task.task_id] = task

    async def nack(self, task: Task, error: str = ""):
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = time.time()

    async def length(self, queue_name: str) -> int:
        return len(self._get_queue(queue_name))

    async def get_result(self, task_id: str) -> Optional[Task]:
        return self._results.get(task_id)


class KafkaQueue(TaskQueueBackend):
    """Kafka-based task queue (production).

    Uses aiokafka for async produce/consume.
    Requires: TASK_QUEUE_BOOTSTRAP_SERVERS env var.
    """

    def __init__(self, bootstrap_servers: str = "", group_id: str = "ai-workers"):
        self._bootstrap = bootstrap_servers or os.getenv("TASK_QUEUE_BOOTSTRAP_SERVERS", "kafka:9092")
        self._group_id = group_id
        self._producer = None
        self._consumers: Dict[str, Any] = {}
        self._initialized = False

    async def _init(self):
        if self._initialized:
            return
        try:
            from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
            )
            await self._producer.start()
            self._initialized = True
            logger.info(f"KafkaQueue: connected to {self._bootstrap}")
        except ImportError:
            logger.warning("aiokafka not installed — falling back to MemoryQueue")
            raise
        except Exception as e:
            logger.warning(f"KafkaQueue init failed: {e} — falling back to MemoryQueue")
            raise

    async def enqueue(self, task: Task) -> str:
        await self._init()
        await self._producer.send_and_wait(
            f"ai-tasks-{task.queue_name}",
            task.to_dict(),
        )
        return task.task_id

    async def dequeue(self, queue_name: str, timeout: float = 1.0) -> Optional[Task]:
        raise NotImplementedError("Use KafkaQueue.start_consumer() to poll in background")

    async def ack(self, task: Task):
        pass  # Kafka offset commit handles this

    async def nack(self, task: Task, error: str = ""):
        pass

    async def length(self, queue_name: str) -> int:
        return -1  # Kafka doesn't expose exact queue length easily

    async def start_consumer(self, queue_name: str,
                             handler: Callable[[Task], Coroutine],
                             concurrency: int = 4):
        """Start a consumer group for continuous task processing."""
        await self._init()
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            f"ai-tasks-{queue_name}",
            bootstrap_servers=self._bootstrap,
            group_id=f"{self._group_id}-{queue_name}",
            value_deserializer=lambda v: json.loads(v.decode()),
            max_poll_records=concurrency,
        )
        await consumer.start()
        self._consumers[queue_name] = consumer

        async def _poll():
            async for msg in consumer:
                task_data = msg.value
                task = Task(
                    task_id=task_data.get("task_id", str(uuid.uuid4())),
                    queue_name=queue_name,
                    payload=task_data.get("payload", {}),
                )
                try:
                    await handler(task)
                except Exception as e:
                    logger.error(f"Task {task.task_id} failed: {e}")

        asyncio.create_task(_poll())
        logger.info(f"KafkaQueue: consumer started for {queue_name}")


def create_queue(backend: str = "") -> TaskQueueBackend:
    """Factory: create the appropriate queue backend.

    Args:
        backend: "memory" (default for dev) or "kafka" (production).
                 Reads TASK_QUEUE_BACKEND env var if not specified.
    """
    backend = backend or os.getenv("TASK_QUEUE_BACKEND", "memory")
    if backend == "kafka":
        kafka = KafkaQueue()
        return kafka
    return MemoryQueue()
