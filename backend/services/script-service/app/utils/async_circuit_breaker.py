"""
异步熔断器 — 保护对外部服务的调用。

当错误率超过阈值时自动熔断，冷却后进入半开状态探测恢复。

用途:
  - LLM API 调用保护 (DeepSeek/OpenAI/Anthropic)
  - 跨服务 HTTP 调用保护
  - 任何可能失败的远程调用
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Awaitable, TypeVar, Any, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """熔断器已打开，请求被拒绝"""
    pass


class AsyncCircuitBreaker:
    """异步熔断器 — 轻量级，适用于 I/O 调用保护。

    三态转换:
      CLOSED ──(错误数≥阈值)──▶ OPEN ──(冷却超时)──▶ HALF_OPEN
       ▲                                                   │
       └────────(探测成功)─────────────────────────────────┘
       └────────(探测失败)──────────────────▶ OPEN
    """

    def __init__(self, name: str = "default",
                 error_threshold: int = 5,
                 reset_timeout: float = 30.0,
                 half_open_max_calls: int = 2):
        self.name = name
        self.error_threshold = error_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._half_open_count = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> BreakerState:
        return self._state

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """执行受保护的异步调用。

        如果熔断器 OPEN，直接抛出 CircuitOpenError。
        如果 HALF_OPEN，允许有限探测请求通过。

        Args:
            func: Async callable to protect.
            *args, **kwargs: Arguments passed to func.

        Returns:
            The function's return value.

        Raises:
            CircuitOpenError: If the breaker is open.
            Original exception: If func fails and breaker stays/trips open.
        """
        async with self._lock:
            # Check/transition state
            if self._state == BreakerState.OPEN:
                if time.time() - self._last_failure_time >= self.reset_timeout:
                    self._state = BreakerState.HALF_OPEN
                    self._half_open_count = 0
                    logger.info(f"Breaker[{self.name}]: OPEN → HALF_OPEN (probing)")
                else:
                    raise CircuitOpenError(
                        f"Breaker[{self.name}] OPEN — rejecting call "
                        f"(reset in {self.reset_timeout - (time.time() - self._last_failure_time):.0f}s)"
                    )

            if self._state == BreakerState.HALF_OPEN:
                if self._half_open_count >= self.half_open_max_calls:
                    raise CircuitOpenError(
                        f"Breaker[{self.name}] HALF_OPEN — probe limit reached"
                    )
                self._half_open_count += 1

        # Execute outside lock to avoid blocking
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self):
        async with self._lock:
            if self._state == BreakerState.HALF_OPEN:
                logger.info(f"Breaker[{self.name}]: HALF_OPEN → CLOSED (probe succeeded)")
            self._state = BreakerState.CLOSED
            self._failure_count = 0
            self._half_open_count = 0

    async def _on_failure(self, error: Exception):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == BreakerState.HALF_OPEN:
                logger.warning(
                    f"Breaker[{self.name}]: HALF_OPEN probe failed → OPEN. "
                    f"Error: {error}"
                )
                self._state = BreakerState.OPEN
            elif self._failure_count >= self.error_threshold:
                logger.warning(
                    f"Breaker[{self.name}]: CLOSED → OPEN "
                    f"({self._failure_count} failures, threshold={self.error_threshold}). "
                    f"Error: {error}"
                )
                self._state = BreakerState.OPEN
            else:
                logger.debug(
                    f"Breaker[{self.name}]: failure {self._failure_count}/{self.error_threshold}"
                )

    async def reset(self):
        """手动重置熔断器到 CLOSED 状态。"""
        async with self._lock:
            self._state = BreakerState.CLOSED
            self._failure_count = 0
            self._half_open_count = 0


# Per-provider circuit breakers
_breakers: dict[str, AsyncCircuitBreaker] = {}


def get_circuit_breaker(name: str = "default",
                        error_threshold: int = 5,
                        reset_timeout: float = 30.0) -> AsyncCircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _breakers:
        _breakers[name] = AsyncCircuitBreaker(
            name=name,
            error_threshold=error_threshold,
            reset_timeout=reset_timeout,
        )
    return _breakers[name]
