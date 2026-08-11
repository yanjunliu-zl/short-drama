"""Async event bus — topic-based pub/sub over RabbitMQ for service decoupling.

Usage (publisher):
    from shared.python.events import EventBus, get_event_bus

    bus = await get_event_bus()
    await bus.publish("script.generation.requested", {
        "task_id": "abc-123",
        "user_id": "user-456",
        "title": "My Short Drama",
    })

Usage (consumer):
    from shared.python.events import EventBus, get_event_bus

    bus = await get_event_bus()
    async for event in bus.subscribe("script.generation.*"):
        print(f"Received: {event.routing_key} -> {event.body}")
        await event.ack()
"""
from .publisher import EventBus, get_event_bus, close_event_bus
from .types import Event, EventHandler

__all__ = ["EventBus", "get_event_bus", "close_event_bus", "Event", "EventHandler"]
