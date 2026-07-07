"""
SSE (Server-Sent Events) streaming utility.
Provides event formatters and a generator helper for FastAPI StreamingResponse.

Usage:
    from app.utils.sse import format_sse_event, stream_tokens_from_llm, EVENT_TOKEN

    # LLM token streaming:
    async for sse_str in stream_tokens_from_llm(llm, messages):
        yield sse_str

    # Custom event:
    yield format_sse_event({"stage": "processing"}, event=EVENT_STAGE)
"""
import json
from typing import AsyncGenerator, Optional, Any


def format_sse_event(
    data: Any,
    event: Optional[str] = None,
    event_id: Optional[str] = None,
) -> str:
    """Format a single SSE event string conforming to the SSE spec.

    Args:
        data: The event payload (will be JSON-serialized).
        event: Optional event type name (e.g. "token", "stage", "done").
        event_id: Optional event identifier for EventSource auto-reconnect.

    Returns:
        SSE-formatted string ending with double newline.
    """
    parts = []
    if event_id is not None:
        parts.append(f"id: {event_id}")
    if event is not None:
        parts.append(f"event: {event}")
    parts.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return "\n".join(parts) + "\n\n"


# ---- Event type constants ----
EVENT_TOKEN    = "token"      # LLM text chunk (token-by-token streaming)
EVENT_STAGE    = "stage"      # Pipeline stage transition (V2 pipeline, per-episode)
EVENT_PROGRESS = "progress"   # Numeric progress update (image/video generation)
EVENT_ERROR    = "error"      # Fatal error — connection closes after this
EVENT_DONE     = "done"       # Completion with optional result payload


# ---- Stream helpers ----

async def stream_tokens_from_llm(
    llm,
    messages: list,
    config: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """Stream LLM token chunks as SSE 'token' events.

    Uses LangChain's astream() which yields AIMessageChunk objects.
    Each chunk is sent as an SSE 'token' event immediately.

    The final token event includes accumulated full text and complete=True.

    Args:
        llm: A LangChain ChatOpenAI instance with streaming=True.
        messages: List of SystemMessage/HumanMessage.
        config: Optional dict passed to llm.astream() (e.g. {"timeout": 180}).

    Yields:
        SSE-formatted 'token' event strings.
    """
    full_text: list[str] = []
    async for chunk in llm.astream(messages, config=config or {}):
        if hasattr(chunk, "content") and chunk.content:
            token = chunk.content
            if isinstance(token, str) and token:
                full_text.append(token)
                yield format_sse_event(
                    {"text": token, "accumulated": "".join(full_text)},
                    event=EVENT_TOKEN,
                )
    # Final token event signalling completion of the LLM stream
    yield format_sse_event(
        {"text": "", "accumulated": "".join(full_text), "complete": True},
        event=EVENT_TOKEN,
    )


async def heartbeat_generator(interval: int = 15):
    """Yield SSE heartbeat comments at regular intervals.

    SSE comment lines (starting with colon) are ignored by clients
    but keep the TCP connection alive through proxies and load balancers.

    Args:
        interval: Seconds between heartbeats.
    """
    import asyncio
    while True:
        await asyncio.sleep(interval)
        yield ": heartbeat\n\n"
