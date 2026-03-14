"""
Retry utilities for external API calls.

Provides:
- retry_with_backoff(): Decorator for automatic retry with exponential backoff and jitter
- CircuitBreaker: Prevents cascading failures by tracking consecutive errors
- with_retry(): Context-free helper for one-off retryable calls

Backoff Strategy
================
Uses full jitter: sleep = random(0, min(cap, base * 2^attempt))
This avoids thundering herd when many workers retry simultaneously.

Circuit Breaker States
======================
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests blocked immediately
- HALF_OPEN: Probe state, one request allowed to test recovery
"""

import functools
import logging
import random
import time
from collections.abc import Callable
from enum import Enum
from threading import Lock
from typing import Any, Optional, Type

logger = logging.getLogger(__name__)


# =============================================================================
# Retry with Exponential Backoff + Jitter
# =============================================================================

def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: tuple[Type[Exception], ...] = (),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
):
    """
    Decorator: retry a function with exponential backoff and full jitter.

    Args:
        max_attempts: Maximum number of total attempts (including the first)
        base_delay: Initial delay in seconds (doubles each attempt)
        max_delay: Maximum delay cap in seconds
        retryable_exceptions: Only retry on these exception types
        non_retryable_exceptions: Never retry on these (takes priority)
        on_retry: Optional callback(attempt_number, exception) called before each retry

    Example::

        @retry_with_backoff(max_attempts=3, base_delay=1.0, retryable_exceptions=(RequestException,))
        def fetch_data():
            return requests.get(url, timeout=10)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Optional[Exception] = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except non_retryable_exceptions as exc:
                    # Don't retry these — re-raise immediately
                    raise
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        break  # Last attempt — don't sleep, just raise below
                    delay = _jitter_delay(attempt, base_delay, max_delay)
                    if on_retry:
                        on_retry(attempt + 1, exc)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_attempts} failed "
                        f"({type(exc).__name__}: {exc}); retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)

            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def _jitter_delay(attempt: int, base: float, cap: float) -> float:
    """Full jitter: random(0, min(cap, base * 2^attempt))."""
    return random.uniform(0, min(cap, base * (2 ** attempt)))


# =============================================================================
# Retry respecting Retry-After header (for 429 rate limits)
# =============================================================================

class RateLimitError(Exception):
    """Raised when an API returns HTTP 429 with a Retry-After value."""
    def __init__(self, retry_after: float = 60.0, message: str = "Rate limited"):
        self.retry_after = retry_after
        super().__init__(message)


def retry_with_rate_limit_respect(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 120.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """
    Like retry_with_backoff but sleeps for Retry-After seconds on RateLimitError.

    If the wrapped function raises RateLimitError(retry_after=N), this decorator
    sleeps for N seconds before retrying rather than using jitter backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Optional[Exception] = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except RateLimitError as exc:
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        break
                    sleep_for = min(exc.retry_after, max_delay)
                    logger.warning(
                        f"{func.__name__} rate limited (attempt {attempt + 1}/{max_attempts}); "
                        f"sleeping {sleep_for:.0f}s (Retry-After)"
                    )
                    time.sleep(sleep_for)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        break
                    delay = _jitter_delay(attempt, base_delay, max_delay)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_attempts} failed "
                        f"({type(exc).__name__}); retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)

            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitState(Enum):
    CLOSED = "closed"        # Normal — all requests pass through
    OPEN = "open"            # Failing — requests blocked immediately
    HALF_OPEN = "half_open"  # Probing — one test request allowed


class CircuitBreakerOpen(Exception):
    """Raised when a circuit breaker is open and the call is blocked."""
    def __init__(self, service: str, reset_in: float):
        self.service = service
        self.reset_in = reset_in
        super().__init__(
            f"Circuit breaker open for '{service}' (resets in {reset_in:.0f}s)"
        )


class CircuitBreaker:
    """
    Thread-safe circuit breaker for protecting external service calls.

    Usage::

        _odds_breaker = CircuitBreaker("odds_api", failure_threshold=3, recovery_timeout=60)

        def fetch_odds():
            with _odds_breaker:
                return requests.get(url, timeout=10)

    States:
    - CLOSED  → requests pass through; consecutive failures increment counter
    - OPEN    → requests blocked for recovery_timeout seconds
    - HALF_OPEN → one probe request; success → CLOSED, failure → OPEN again
    """

    def __init__(
        self,
        service: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        self.service = service
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._get_state()

    def _get_state(self) -> CircuitState:
        """Internal: check if OPEN circuit should transition to HALF_OPEN."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._last_failure_time or 0)
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.service}' → HALF_OPEN (probing)")
        return self._state

    def __enter__(self):
        with self._lock:
            state = self._get_state()
            if state == CircuitState.OPEN:
                elapsed = time.monotonic() - (self._last_failure_time or 0)
                reset_in = max(0.0, self.recovery_timeout - elapsed)
                raise CircuitBreakerOpen(self.service, reset_in)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._on_success()
        elif exc_type is not CircuitBreakerOpen:
            self._on_failure()
        return False  # Don't suppress exceptions

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit breaker '{self.service}' → CLOSED (recovered)")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if (
                self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker '{self.service}' → OPEN "
                    f"({self._failure_count} consecutive failures)"
                )

    def get_stats(self) -> dict[str, Any]:
        """Return current circuit breaker state for health checks / logging."""
        with self._lock:
            return {
                "service": self.service,
                "state": self._get_state().value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "last_failure_ago": (
                    round(time.monotonic() - self._last_failure_time, 1)
                    if self._last_failure_time
                    else None
                ),
            }


# =============================================================================
# Module-level circuit breakers for shared services
# =============================================================================

# These are singletons — imported and reused across the process lifetime.
odds_api_breaker = CircuitBreaker("odds_api", failure_threshold=3, recovery_timeout=120.0)
espn_breaker = CircuitBreaker("espn", failure_threshold=3, recovery_timeout=60.0)
haslametrics_breaker = CircuitBreaker("haslametrics", failure_threshold=3, recovery_timeout=60.0)
claude_breaker = CircuitBreaker("claude", failure_threshold=5, recovery_timeout=30.0)
grok_breaker = CircuitBreaker("grok", failure_threshold=5, recovery_timeout=30.0)


def get_all_circuit_stats() -> list[dict]:
    """Return stats for all registered circuit breakers (for health endpoints)."""
    return [
        odds_api_breaker.get_stats(),
        espn_breaker.get_stats(),
        haslametrics_breaker.get_stats(),
        claude_breaker.get_stats(),
        grok_breaker.get_stats(),
    ]
