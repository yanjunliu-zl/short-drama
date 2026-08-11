"""Event type definitions for the async event bus."""
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from aio_pika import IncomingMessage


@dataclass
class Event:
    """A domain event on the message bus."""
    routing_key: str
    body: Dict[str, Any]
    message: Optional[IncomingMessage] = None

    async def ack(self):
        """Acknowledge the message (remove from queue)."""
        if self.message:
            await self.message.ack()

    async def nack(self, requeue: bool = True):
        """Negative-acknowledge (reject and optionally requeue)."""
        if self.message:
            await self.message.nack(requeue=requeue)

    @classmethod
    def from_message(cls, msg: IncomingMessage) -> "Event":
        return cls(
            routing_key=msg.routing_key or "",
            body=json.loads(msg.body.decode()) if msg.body else {},
            message=msg,
        )


# Event handler callback type
EventHandler = Callable[[Event], Any]
