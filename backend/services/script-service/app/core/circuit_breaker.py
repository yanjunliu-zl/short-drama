"""Circuit Breaker 实现"""
import time
from enum import Enum
from typing import Callable, Optional, TypeVar, Any
from threading import Lock


class CircuitState(Enum):
    CLOSED = "closed"      # 正常状态，请求通过
    OPEN = "open"          # 熔断状态，请求失败
    HALF_OPEN = "half_open"  # 半开状态，尝试允许请求通过


class CircuitBreakerError(Exception):
    """断路器异常"""
    pass


T = TypeVar('T')


class CircuitBreaker:
    """断路器实现"""

    def __init__(
        self,
        error_threshold: int = 5,
        reset_timeout: int = 30,
        half_open_max_calls: int = 1
    ):
        self.error_threshold = error_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # 检查是否应该切换到半开状态
                if (self._last_failure_time and
                    time.time() - self._last_failure_time >= self.reset_timeout):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def _record_success(self) -> None:
        """记录成功"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    # 成功次数达到阈值，关闭断路器
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _record_failure(self) -> None:
        """记录失败"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下失败，重新打开断路器
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.error_threshold:
                    self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """检查是否可以执行请求"""
        return self.state != CircuitState.OPEN

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """执行函数，带断路器保护"""
        if not self.can_execute():
            raise CircuitBreakerError(
                f"Circuit breaker is {self.state.value}, request rejected"
            )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def reset(self) -> None:
        """重置断路器"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0


# 全局断路器实例
circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str = "default") -> CircuitBreaker:
    """获取断路器实例"""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker()
    return circuit_breakers[name]


def circuit_breaker(
    name: str = "default",
    error_threshold: int = 5,
    reset_timeout: int = 30
):
    """断路器装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs):
            cb = CircuitBreaker(
                error_threshold=error_threshold,
                reset_timeout=reset_timeout
            )
            return cb.execute(func, *args, **kwargs)
        return wrapper
    return decorator
