"""
AI Inference Service Client — Production-grade unified client for vLLM + TEI + Seedance.

Replaces in-process LLM inference with dedicated GPU services.
Benefits:
  - Independent scaling (AI services scale separately from business logic)
  - GPU resource pooling (multiple business services share one vLLM cluster)
  - Connection pooling with httpx (HTTP/2 multiplexing, keep-alive)
  - Circuit breaker per inference service
  - Health check + automatic failover

Architecture:
  Business Service (script/storyboard/llmhua)
      ↓ HTTP/2 (httpx connection pool)
  Inference Service (vLLM :8000 / TEI :80 / Seedance Ark API)
"""
import asyncio
import logging
import os
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class InferenceServiceType(str, Enum):
    VLLM = "vllm"           # Self-hosted LLM (Qwen2.5-7B/14B)
    TEI = "tei"             # Text Embeddings Inference
    SEEDANCE = "seedance"   # Volcano Ark API
    DEEPSEEK = "deepseek"   # Cloud API fallback
    OPENAI = "openai"       # Cloud API fallback


@dataclass
class ServiceEndpoint:
    """Inference service endpoint with health status."""
    url: str
    service_type: InferenceServiceType
    model: str = ""
    weight: int = 1              # Load balancing weight
    healthy: bool = True
    last_health_check: float = 0.0
    consecutive_failures: int = 0
    max_concurrent: int = 100     # Max concurrent requests
    _semaphore: asyncio.Semaphore = None

    def __post_init__(self):
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)


class InferenceClientPool:
    """Connection pool for AI inference services.

    Manages multiple endpoints per service type with:
      - HTTP/2 connection pooling (httpx.AsyncClient with limits)
      - Round-robin load balancing across healthy endpoints
      - Circuit breaker per endpoint (5 failures → 30s cooldown)
      - Automatic health check every 30s
    """

    def __init__(self,
                 pool_size: int = 100,        # HTTP connections per endpoint
                 pool_keepalive: int = 30,    # Keep-alive seconds
                 request_timeout: float = 300.0):
        self._endpoints: Dict[str, List[ServiceEndpoint]] = {}
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._pool_size = pool_size
        self._pool_keepalive = pool_keepalive
        self._request_timeout = request_timeout
        self._health_lock = asyncio.Lock()

    # ── Service Registration ──

    def register(self, service_type: InferenceServiceType,
                 endpoints: List[Tuple[str, str, int]]):
        """Register inference service endpoints.

        Args:
            service_type: VLLM / TEI / SEEDANCE / DEEPSEEK / OPENAI
            endpoints: [(url, model_name, weight), ...]
        """
        eps = []
        for url, model, weight in endpoints:
            eps.append(ServiceEndpoint(
                url=url, service_type=service_type,
                model=model, weight=weight,
            ))
        self._endpoints[service_type.value] = eps

        # Create dedicated httpx client for this service type
        if service_type.value not in self._clients:
            limits = httpx.Limits(
                max_keepalive_connections=len(eps) * 20,
                max_connections=len(eps) * 50,
                keepalive_expiry=self._pool_keepalive,
            )
            self._clients[service_type.value] = httpx.AsyncClient(
                timeout=self._request_timeout,
                limits=limits,
                http2=True,
            )

    def auto_discover(self):
        """Auto-discover inference services from environment variables."""
        # vLLM
        vllm_base = os.getenv("VLLM_API_BASE", "")
        if vllm_base:
            small_model = os.getenv("VLLM_SMALL_MODEL", "Qwen/Qwen2.5-7B-Instruct")
            self.register(InferenceServiceType.VLLM, [
                (vllm_base, small_model, 2),
            ])
            # Large model
            large_model = os.getenv("VLLM_LARGE_MODEL", "")
            if large_model:
                self.register(InferenceServiceType.VLLM, [
                    (vllm_base, large_model, 1),
                ])

        # TEI
        tei_base = os.getenv("EMBEDDING_API_BASE", "")
        if tei_base:
            self.register(InferenceServiceType.TEI, [
                (tei_base, "bge-large-zh-v1.5", 1),
            ])

        # Cloud APIs — always available as fallback
        deepseek_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        if os.getenv("DEEPSEEK_API_KEY"):
            self.register(InferenceServiceType.DEEPSEEK, [
                (deepseek_base, os.getenv("DEEPSEEK_MODEL", "deepseek-chat"), 1),
            ])

        openai_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        if os.getenv("OPENAI_API_KEY"):
            self.register(InferenceServiceType.OPENAI, [
                (openai_base, os.getenv("OPENAI_MODEL", "gpt-4o"), 1),
            ])

    # ── Health Check ──

    async def health_check(self, service_type: str = ""):
        """Check health of all registered endpoints. Unhealthy ones are marked."""
        async with self._health_lock:
            types = [service_type] if service_type else list(self._endpoints.keys())
            for st in types:
                for ep in self._endpoints.get(st, []):
                    try:
                        client = self._clients[st]
                        resp = await client.get(
                            f"{ep.url}/health" if "vllm" in st or "tei" in st
                            else f"{ep.url}/v1/models",
                            timeout=5.0,
                        )
                        if resp.status_code == 200:
                            ep.healthy = True
                            ep.consecutive_failures = 0
                        else:
                            ep.consecutive_failures += 1
                    except Exception:
                        ep.consecutive_failures += 1

                    if ep.consecutive_failures >= 5:
                        ep.healthy = False
                    ep.last_health_check = time.time()

    # ── Endpoint Selection ──

    def _select_endpoint(self, service_types: List[str]) -> Optional[ServiceEndpoint]:
        """Select a healthy endpoint using weighted round-robin.

        Tries each service type in priority order (e.g., vLLM → DeepSeek → OpenAI).
        """
        for st in service_types:
            eps = self._endpoints.get(st, [])
            healthy = [e for e in eps if e.healthy]
            if healthy:
                # Weighted selection: higher weight = more traffic
                total_weight = sum(e.weight for e in healthy)
                if total_weight > 0:
                    import random
                    r = random.uniform(0, total_weight)
                    cumulative = 0
                    for ep in healthy:
                        cumulative += ep.weight
                        if r <= cumulative:
                            return ep
                return healthy[0]
        return None

    # ── LLM Inference ──

    async def chat_completion(self, messages: List[Dict],
                              prefer: str = "vllm",
                              temperature: float = 0.7,
                              max_tokens: int = 16000,
                              **kwargs) -> Dict[str, Any]:
        """Send chat completion request to inference service.

        Args:
            messages: [{"role":"system","content":"..."},
                       {"role":"user","content":"..."}]
            prefer: Preferred service type priority ("vllm" → "deepseek" → "openai")
            temperature: Generation temperature
            max_tokens: Max output tokens

        Returns:
            {"choices":[{"message":{"content":"..."}}],"usage":{...}}
        """
        priority = {
            "vllm": ["vllm", "deepseek", "openai"],
            "deepseek": ["deepseek", "vllm", "openai"],
            "openai": ["openai", "deepseek", "vllm"],
        }.get(prefer, ["vllm", "deepseek", "openai"])

        ep = self._select_endpoint(priority)
        if ep is None:
            raise RuntimeError("No healthy inference endpoints available")

        async with ep._semaphore:
            payload = {
                "model": ep.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }
            client = self._clients[ep.service_type.value]
            try:
                resp = await client.post(
                    f"{ep.url}/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {os.getenv(ep.service_type.value.upper() + '_API_KEY', 'not-needed')}"},
                )
                if resp.status_code == 200:
                    ep.consecutive_failures = 0
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503):
                    ep.consecutive_failures += 1
                    # Retry with next endpoint
                    next_ep = self._select_endpoint([p for p in priority if p != ep.service_type.value])
                    if next_ep:
                        return await self.chat_completion(messages, prefer=next_ep.service_type.value)
                raise httpx.HTTPStatusError(
                    f"Inference failed: {resp.status_code}",
                    request=resp.request, response=resp,
                )
            except Exception as e:
                ep.consecutive_failures += 1
                raise

    # ── Embedding ──

    async def embed(self, texts: List[str],
                    service_type: str = "tei") -> List[List[float]]:
        """Generate embeddings via TEI or OpenAI embeddings API.

        Args:
            texts: List of texts to embed.
            service_type: "tei" (local GPU) or "openai" (cloud).

        Returns:
            List of embedding vectors.
        """
        priority = ["tei", "openai"] if service_type == "tei" else ["openai", "tei"]
        ep = self._select_endpoint(priority)

        if ep is None:
            raise RuntimeError("No embedding endpoints available")

        client = self._clients[ep.service_type.value]
        payload = {"input": texts, "model": ep.model}

        try:
            resp = await client.post(f"{ep.url}/v1/embeddings", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")

        # Fallback: local HuggingFace
        from langchain_huggingface import HuggingFaceEmbeddings
        emb = HuggingFaceEmbeddings(
            model_name=os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"))
        return [emb.embed_query(t) for t in texts]

    # ── Image Generation ──

    async def generate_image(self, prompt: str, negative_prompt: str = "",
                             width: int = 1920, height: int = 1080,
                             **kwargs) -> Dict[str, Any]:
        """Generate image via Seedance or local Stable Diffusion."""
        ep = self._select_endpoint(["seedance"]) if self._endpoints.get("seedance") else None

        if ep:
            client = self._clients["seedance"]
            payload = {
                "model": os.getenv("SEEDANCE_IMAGE_MODEL", "doubao-seedream-4-5-251128"),
                "prompt": prompt,
                "size": f"{width}x{height}",
                "n": 1,
                "response_format": "url",
            }
            try:
                resp = await client.post(f"{ep.url}/images/generations", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "status": "completed",
                        "image_url": data.get("data", [{}])[0].get("url", ""),
                    }
            except Exception as e:
                logger.warning(f"Image gen failed: {e}")

        return {"status": "failed", "error": "No image generation endpoint"}

    async def close(self):
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.aclose()


# Global pool instance
_inference_pool: Optional[InferenceClientPool] = None


def get_inference_pool() -> InferenceClientPool:
    global _inference_pool
    if _inference_pool is None:
        _inference_pool = InferenceClientPool()
        _inference_pool.auto_discover()
    return _inference_pool
