"""EventBus — async topic-based pub/sub over RabbitMQ.

Uses aio_pika for async AMQP operations.
Connects to RabbitMQ and declares a topic exchange for service decoupling.

Event routing key conventions:
    {domain}.{entity}.{action}
    Examples:
        script.generation.requested
        script.generation.completed
        image.generation.requested
        image.generation.completed
        video.processing.completed
        final_cut.completed
"""
import json
import logging
from typing import AsyncIterator, Dict, Any, Optional

import aio_pika

logger = logging.getLogger(__name__)

# Topic exchange name
EXCHANGE_NAME = "shortdrama.events"

# Event routing keys
class EventKeys:
    SCRIPT_GENERATION_REQUESTED = "script.generation.requested"
    SCRIPT_GENERATION_COMPLETED = "script.generation.completed"
    SCRIPT_GENERATION_FAILED = "script.generation.failed"
    IMAGE_GENERATION_REQUESTED = "image.generation.requested"
    IMAGE_GENERATION_COMPLETED = "image.generation.completed"
    IMAGE_GENERATION_FAILED = "image.generation.failed"
    VIDEO_PROCESSING_COMPLETED = "video.processing.completed"
    VIDEO_PROCESSING_FAILED = "video.processing.failed"
    FINAL_CUT_COMPLETED = "final_cut.completed"
    FINAL_CUT_FAILED = "final_cut.failed"
    STORYBOARD_COMPLETED = "storyboard.completed"
    USER_REGISTERED = "user.registered"


class EventBus:
    """Async pub/sub event bus over RabbitMQ topic exchange."""

    def __init__(self, url: str):
        self.url = url
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.RobustChannel] = None
        self.exchange: Optional[aio_pika.RobustExchange] = None

    async def connect(self):
        """Connect to RabbitMQ and declare the topic exchange."""
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            EXCHANGE_NAME,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("EventBus connected to RabbitMQ, exchange=%s", EXCHANGE_NAME)

    async def close(self):
        """Close the connection."""
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()
        logger.info("EventBus disconnected")

    async def publish(self, routing_key: str, data: Dict[str, Any]):
        """Publish an event to the topic exchange.

        Args:
            routing_key: Event routing key (e.g., 'script.generation.requested')
            data: Event payload as a dictionary
        """
        if not self.exchange:
            raise RuntimeError("EventBus not connected. Call await bus.connect() first.")

        message = aio_pika.Message(
            body=json.dumps(data, ensure_ascii=False).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.exchange.publish(message, routing_key=routing_key)
        logger.debug("Published event: %s", routing_key)

    async def subscribe(self, routing_key_pattern: str) -> AsyncIterator:
        """Subscribe to events matching the routing key pattern.

        Args:
            routing_key_pattern: Pattern like 'script.generation.*' or '*.completed'

        Yields:
            Event objects as they arrive
        """
        if not self.channel:
            raise RuntimeError("EventBus not connected. Call await bus.connect() first.")

        # Declare a temporary auto-delete queue for this subscriber
        queue = await self.channel.declare_queue(exclusive=True, auto_delete=True)
        await queue.bind(self.exchange, routing_key=routing_key_pattern)

        logger.info("Subscribed to events: %s (queue=%s)", routing_key_pattern, queue.name)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    from .types import Event
                    yield Event.from_message(message)


# Global singleton
_event_bus: Optional[EventBus] = None


async def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        from app.core.config import settings
        url = (
            f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}"
            f"@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}//"
        )
        _event_bus = EventBus(url)
        await _event_bus.connect()
    return _event_bus


async def close_event_bus():
    """Close the global EventBus connection."""
    global _event_bus
    if _event_bus:
        await _event_bus.close()
        _event_bus = None
