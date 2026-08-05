"""
Short Drama Platform — Shared AI modules.

Canonical versions of shared utilities used across all AI services.
Each service's Docker build should copy this directory into the container.

Modules:
    model_router.py  — Multi-model provider fallback (DeepSeek → OpenAI → Anthropic)
    usage_tracker.py — AI usage tracking with real token extraction and cost calculation
    sse.py           — Server-Sent Events formatting and streaming helpers

Usage (in a service's Dockerfile):
    COPY ../shared/python /app/shared/
    # Then in Python:
    # import sys; sys.path.insert(0, '/app/shared')
    # from model_router import create_llm_client
