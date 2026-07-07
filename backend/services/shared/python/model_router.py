"""
Multi-model fallback router for LLM provider resilience.

Creates a ChatOpenAI client by trying providers in priority order:
  1. DeepSeek (deepseek-chat) — primary, lowest cost
  2. OpenAI (gpt-4o) — first fallback
  3. Anthropic (claude-sonnet-5) — second fallback via OpenAI-compatible API
  4. Mock mode — last resort, returns placeholder data

On initialization, the first provider with a valid API key is selected.
On runtime errors (auth/rate-limit/server), a provider switch is triggered.

Usage:
    from app.utils.model_router import create_llm_client

    llm = create_llm_client(prefer="deepseek")
    response = await llm.ainvoke(messages)

    # Check active provider:
    from app.utils.model_router import get_active_provider
    print(get_active_provider())  # "deepseek" | "openai" | "anthropic" | "mock"
"""
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Global tracker for active provider
_active_provider: str = "uninitialized"
_active_client_info: Dict[str, Any] = {}


def _create_httpx_clients(base_url: str, timeout: float = 180.0):
    """Create httpx sync+async clients for LangChain ChatOpenAI."""
    import httpx
    http_client = httpx.Client(base_url=base_url, timeout=timeout)
    http_async_client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
    return http_client, http_async_client


def _try_create_deepseek(timeout: float = 180.0) -> Optional[Any]:
    """Try to create a DeepSeek ChatOpenAI client."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.debug("DeepSeek: no API key configured, skipping")
        return None

    api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    http_client, http_async_client = _create_httpx_clients(api_base, timeout)

    try:
        llm = ChatOpenAI(
            model_name=model,
            openai_api_key=api_key,
            openai_api_base=api_base,
            temperature=0.7,
            max_tokens=16000,
            timeout=timeout,
            max_retries=1,
            streaming=True,
            http_client=http_client,
            http_async_client=http_async_client,
            model_kwargs={"extra_body": {"cache_prefix": True}},
        )
        logger.info(f"ModelRouter: DeepSeek ✓ (model={model}, base={api_base})")
        return llm
    except Exception as e:
        logger.warning(f"DeepSeek: init failed: {e}")
        return None


def _try_create_openai(timeout: float = 180.0) -> Optional[Any]:
    """Try to create an OpenAI ChatOpenAI client."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.debug("OpenAI: no API key configured, skipping")
        return None

    api_base = os.getenv("OPENAI_API_BASE", None)
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    http_client, http_async_client = _create_httpx_clients(
        api_base or "https://api.openai.com/v1", timeout
    )

    try:
        kwargs = {
            "model_name": model,
            "openai_api_key": api_key,
            "timeout": timeout,
            "max_retries": 1,
            "streaming": True,
            "http_client": http_client,
            "http_async_client": http_async_client,
        }
        if api_base:
            kwargs["openai_api_base"] = api_base
        llm = ChatOpenAI(**kwargs)
        logger.info(f"ModelRouter: OpenAI ✓ (model={model})")
        return llm
    except Exception as e:
        logger.warning(f"OpenAI: init failed: {e}")
        return None


def _try_create_anthropic(timeout: float = 180.0) -> Optional[Any]:
    """Try to create an Anthropic client (ChatAnthropic or via proxy).

    Supports two modes:
      a) Direct: ANTHROPIC_API_KEY + langchain-anthropic
      b) Via OpenAI-compatible proxy: ANTHROPIC_API_BASE + ANTHROPIC_API_KEY
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.debug("Anthropic: no API key configured, skipping")
        return None

    # Mode A: Direct Anthropic SDK
    api_base = os.getenv("ANTHROPIC_API_BASE", "")
    if api_base:
        # Use via OpenAI-compatible proxy
        from langchain_openai import ChatOpenAI
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
        http_client, http_async_client = _create_httpx_clients(api_base, timeout)
        try:
            llm = ChatOpenAI(
                model_name=model,
                openai_api_key=api_key,
                openai_api_base=api_base,
                timeout=timeout,
                max_retries=1,
                streaming=True,
                http_client=http_client,
                http_async_client=http_async_client,
            )
            logger.info(f"ModelRouter: Anthropic ✓ via proxy (model={model})")
            return llm
        except Exception as e:
            logger.warning(f"Anthropic proxy init failed: {e}")

    # Mode B: Direct Anthropic SDK
    try:
        from langchain_anthropic import ChatAnthropic
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
        llm = ChatAnthropic(
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_retries=1,
        )
        logger.info(f"ModelRouter: Anthropic ✓ direct (model={model})")
        return llm
    except ImportError:
        logger.debug("Anthropic: langchain-anthropic not installed, direct mode unavailable")
    except Exception as e:
        logger.warning(f"Anthropic direct init failed: {e}")

    return None


def _try_create_vllm(timeout: float = 180.0) -> Optional[Any]:
    """Try to create a client for self-hosted vLLM/TGI server.

    vLLM/TGI expose an OpenAI-compatible API at VLLM_API_BASE.
    Supports tiered models:
      - VLLM_SMALL_MODEL: for simple tasks (e.g. Qwen2.5-7B)
      - VLLM_LARGE_MODEL: for complex tasks (e.g. Qwen2.5-14B)

    Set VLLM_API_BASE to enable (e.g. http://vllm-server:8000/v1).
    """
    from langchain_openai import ChatOpenAI

    api_base = os.getenv("VLLM_API_BASE", "")
    if not api_base:
        return None

    api_key = os.getenv("VLLM_API_KEY", "not-needed")
    model = os.getenv("VLLM_SMALL_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    http_client, http_async_client = _create_httpx_clients(api_base, timeout)

    try:
        llm = ChatOpenAI(
            model_name=model,
            openai_api_key=api_key,
            openai_api_base=api_base,
            temperature=0.7,
            max_tokens=8000,
            timeout=timeout,
            max_retries=1,
            streaming=True,
            http_client=http_client,
            http_async_client=http_async_client,
        )
        logger.info(f"ModelRouter: vLLM ✓ (model={model}, base={api_base})")
        return llm
    except Exception as e:
        logger.warning(f"vLLM init failed: {e}")
        return None


class TieredModelRouter:
    """3-tier model routing: Small(local) → Large(local) → Cloud(DeepSeek).

    Usage:
        router = TieredModelRouter()
        llm = await router.get_llm("simple")  # → vLLM 7B
        llm = await router.get_llm("complex") # → DeepSeek
    """

    def __init__(self, timeout: float = 180.0):
        self._timeout = timeout
        self._small_llm = None
        self._large_llm = None
        self._cloud_llm = None

    async def get_llm(self, tier: str = "auto") -> Any:
        """Get LLM for given tier: 'simple', 'medium', 'complex', or 'auto'.

        'auto' tries: cloud → vLLM large → vLLM small.
        """
        if tier == "simple":
            return self._get_small() or self._get_cloud()
        elif tier == "medium":
            return self._get_large() or self._get_small() or self._get_cloud()
        elif tier == "complex":
            return self._get_cloud()
        else:  # auto
            return self._get_cloud() or self._get_large() or self._get_small()

    def _get_small(self):
        if self._small_llm is None:
            os.environ["VLLM_SMALL_MODEL"] = os.getenv("VLLM_SMALL_MODEL", "Qwen/Qwen2.5-7B-Instruct")
            self._small_llm = _try_create_vllm(timeout=self._timeout)
        return self._small_llm

    def _get_large(self):
        if self._large_llm is None:
            saved = os.getenv("VLLM_SMALL_MODEL", "")
            os.environ["VLLM_SMALL_MODEL"] = os.getenv("VLLM_LARGE_MODEL", "Qwen/Qwen2.5-14B-Instruct")
            self._large_llm = _try_create_vllm(timeout=self._timeout)
            os.environ["VLLM_SMALL_MODEL"] = saved
        return self._large_llm

    def _get_cloud(self):
        if self._cloud_llm is None:
            self._cloud_llm = _try_create_deepseek(timeout=self._timeout) or \
                              _try_create_openai(timeout=self._timeout) or \
                              _try_create_anthropic(timeout=self._timeout)
        return self._cloud_llm


def create_llm_client(prefer: str = "deepseek", timeout: float = 180.0):
    """Create an LLM client with automatic provider fallback.

    Tries providers in priority order: deepseek → openai → anthropic.
    Returns a ChatOpenAI-like client or None (mock mode).

    Args:
        prefer: Preferred provider: "deepseek", "openai", or "anthropic".
                Providers are tried in this order regardless.
        timeout: HTTP timeout in seconds.

    Returns:
        A LangChain chat model instance, or None if no provider is available.
    """
    global _active_provider, _active_client_info

    providers = [
        ("deepseek", _try_create_deepseek),
        ("openai", _try_create_openai),
        ("anthropic", _try_create_anthropic),
    ]

    # Reorder: put preferred provider first
    if prefer and prefer != "deepseek":
        for i, (name, _) in enumerate(providers):
            if name == prefer:
                providers.insert(0, providers.pop(i))
                break

    for name, factory in providers:
        llm = factory(timeout=timeout)
        if llm is not None:
            _active_provider = name
            _active_client_info = {
                "provider": name,
                "healthy": True,
            }
            return llm

    logger.warning("ModelRouter: No LLM provider available — using mock mode")
    _active_provider = "mock"
    _active_client_info = {"provider": "mock", "healthy": False}
    return None


# ================================================================
# ResilientLLM — runtime provider failover wrapper
# ================================================================

_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504, 529}
_FALLBACK_PROVIDERS = ["openai", "anthropic", "deepseek"]


class ResilientLLM:
    """Wraps a LangChain ChatOpenAI client with runtime provider failover.

    On 429 (rate-limit) or 5xx (server error), automatically:
      1. Marks the current provider as unhealthy
      2. Tries the next available provider
      3. Transparently retries the failed call
      4. Periodically probes the preferred provider for recovery
    """

    def __init__(self, primary_llm, provider_name: str = "deepseek", timeout: float = 180.0):
        self._llm = primary_llm
        self._provider = provider_name
        self._timeout = timeout
        self._fallback_llms: Dict[str, Any] = {}
        self._unhealthy: Dict[str, float] = {}  # provider → cooldown_until timestamp
        self._probe_interval = 60.0  # seconds before retrying an unhealthy provider

    def _try_create_fallback(self, name: str):
        """Lazy-create a fallback LLM client."""
        if name in self._fallback_llms and self._fallback_llms[name] is not None:
            return self._fallback_llms[name]

        factories = {
            "deepseek": _try_create_deepseek,
            "openai": _try_create_openai,
            "anthropic": _try_create_anthropic,
        }
        factory = factories.get(name)
        if factory:
            llm = factory(timeout=self._timeout)
            self._fallback_llms[name] = llm
            if llm:
                logger.info(f"ResilientLLM: fallback {name} ready")
            return llm
        return None

    def _switch_provider(self) -> bool:
        """Try to switch to a healthy fallback provider. Returns True on success."""
        import time
        now = time.time()

        for name in _FALLBACK_PROVIDERS:
            if name == self._provider:
                continue
            # Skip providers in cooldown
            if name in self._unhealthy and now < self._unhealthy[name]:
                continue
            fallback = self._try_create_fallback(name)
            if fallback is not None:
                logger.warning(
                    f"ResilientLLM: switching {self._provider} → {name} "
                    f"(previous provider failed)"
                )
                self._provider = name
                self._llm = fallback
                global _active_provider
                _active_provider = name
                return True

        return False

    def _mark_unhealthy(self):
        """Mark current provider as unhealthy with cooldown."""
        import time
        self._unhealthy[self._provider] = time.time() + self._probe_interval
        logger.warning(f"ResilientLLM: {self._provider} marked unhealthy for {self._probe_interval}s")

    def _mark_healthy(self):
        """Clear cooldown for current provider."""
        self._unhealthy.pop(self._provider, None)

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable (rate-limit or server error)."""
        error_str = str(error).lower()
        # httpx.HTTPStatusError
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            return error.response.status_code in _RETRYABLE_HTTP_CODES
        # String-based detection for wrapped errors
        for code in _RETRYABLE_HTTP_CODES:
            if str(code) in error_str:
                return True
        # Common patterns
        if any(kw in error_str for kw in [
            'rate limit', 'too many requests', 'service unavailable',
            'server error', 'internal server error', 'bad gateway',
            'gateway timeout', 'overloaded',
        ]):
            return True
        return False

    async def ainvoke(self, messages, config: dict = None):
        """Async invoke with circuit breaker + automatic failover."""
        from async_circuit_breaker import get_circuit_breaker, CircuitOpenError

        breaker = get_circuit_breaker(f"llm-{self._provider}")
        last_error = None
        tried = set()
        for attempt in range(3):
            tried.add(self._provider)
            try:
                result = await breaker.call(
                    self._llm.ainvoke, messages, config=config or {}
                )
                self._mark_healthy()
                return result
            except CircuitOpenError:
                logger.warning(f"ResilientLLM: {self._provider} breaker OPEN, switching provider")
                self._mark_unhealthy()
                if not self._switch_provider():
                    raise
                breaker = get_circuit_breaker(f"llm-{self._provider}")
            except Exception as e:
                last_error = e
                if self._is_retryable_error(e):
                    logger.warning(
                        f"ResilientLLM: {self._provider} ainvoke failed (attempt {attempt+1}/3): {e}"
                    )
                    self._mark_unhealthy()
                    if not self._switch_provider():
                        break
                    breaker = get_circuit_breaker(f"llm-{self._provider}")
                else:
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("ResilientLLM: all providers exhausted")

    async def astream(self, messages, config: dict = None):
        """Async stream with automatic failover on retryable errors."""
        last_error = None
        tried = set()
        for attempt in range(3):
            tried.add(self._provider)
            try:
                async for chunk in self._llm.astream(messages, config=config or {}):
                    yield chunk
                self._mark_healthy()
                return
            except Exception as e:
                last_error = e
                if self._is_retryable_error(e):
                    logger.warning(
                        f"ResilientLLM: {self._provider} astream failed (attempt {attempt+1}/3): {e}"
                    )
                    self._mark_unhealthy()
                    if not self._switch_provider():
                        break
                else:
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("ResilientLLM: all providers exhausted")

    def with_structured_output(self, schema, method: str = "json_mode"):
        """Pass-through for LangChain structured output."""
        return self._llm.with_structured_output(schema, method=method)

    @property
    def provider(self) -> str:
        return self._provider


def create_llm_client(prefer: str = "deepseek", timeout: float = 180.0):
    """Create a resilient LLM client with automatic provider fallback.

    Returns a ResilientLLM wrapping the best available provider.
    Runtime errors (429, 5xx) trigger automatic provider switching.

    Returns None if no provider is available (mock mode).
    """
    global _active_provider, _active_client_info

    providers = [
        ("deepseek", _try_create_deepseek),
        ("openai", _try_create_openai),
        ("anthropic", _try_create_anthropic),
    ]

    if prefer and prefer != "deepseek":
        for i, (name, _) in enumerate(providers):
            if name == prefer:
                providers.insert(0, providers.pop(i))
                break

    for name, factory in providers:
        llm = factory(timeout=timeout)
        if llm is not None:
            _active_provider = name
            _active_client_info = {"provider": name, "healthy": True}
            resilient = ResilientLLM(llm, provider_name=name, timeout=timeout)
            logger.info(f"ModelRouter: {name} ✓ (resilient, with runtime failover)")
            return resilient

    logger.warning("ModelRouter: No LLM provider available — using mock mode")
    _active_provider = "mock"
    _active_client_info = {"provider": "mock", "healthy": False}
    return None


def get_active_provider() -> str:
    """Return the currently active LLM provider name."""
    return _active_provider


def get_provider_info() -> Dict[str, Any]:
    """Return info about the currently active LLM provider."""
    return dict(_active_client_info)


def provider_is_healthy() -> bool:
    """Check if any real provider is active (not mock)."""
    return _active_provider not in ("uninitialized", "mock")
