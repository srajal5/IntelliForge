"""
Retry utility powered by tenacity.

Provides a reusable decorator and a helper for wrapping async callables
with exponential back-off and configurable retry counts.
"""

from __future__ import annotations

from typing import TypeVar, Callable, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[..., Any]:
    """Return a tenacity retry decorator with sensible defaults.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay cap in seconds.
        retryable_exceptions: Tuple of exception types that trigger a retry.

    Returns:
        A decorator that can be applied to sync or async functions.

    Example::

        @with_retry(max_attempts=5)
        async def fetch_data(url: str) -> dict:
            ...
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=base_delay, max=max_delay),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=before_sleep_log(logger, "WARNING"),  # type: ignore[arg-type]
        reraise=True,
    )
