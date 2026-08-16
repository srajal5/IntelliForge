"""Retry and exponential backoff utilities with jitter for LLM API calls."""

from __future__ import annotations

import asyncio
import random
from typing import Callable, TypeVar

from src.llm.exceptions import (
    AuthenticationError,
    OversizedRequestError,
    RateLimitError,
    TimeoutError,
    ProviderError,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def calculate_backoff_delay(attempt: int, base: float = 2.0, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff delay with uniform jitter.

    Formula: min(max_delay, base ^ attempt) + uniform_random(0.0, 0.5 * delay)
    """
    exponential = base ** max(0, attempt - 1)
    capped = min(max_delay, exponential)
    jitter = random.uniform(0.0, 0.5 * capped)
    return round(capped + jitter, 3)


async def execute_with_retry(
    coro_fn: Callable[[], asyncio.Future[T] | Coroutine[Any, Any, T]],
    provider_name: str,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    backoff_max: float = 30.0,
) -> T:
    """Execute an async coroutine function with retry logic and exponential backoff.

    Retries on: RateLimitError (429), TimeoutError (408), ProviderError (5xx).
    Does NOT retry on: AuthenticationError (401/403) or OversizedRequestError (413).
    """
    attempt = 1
    last_error: Exception | None = None

    while attempt <= max_retries:
        try:
            return await coro_fn()
        except (AuthenticationError, OversizedRequestError) as exc:
            # Permanent failures: Do NOT retry on this provider
            logger.error("llm_permanent_failure_no_retry", provider=provider_name, error=str(exc))
            raise exc
        except (RateLimitError, TimeoutError, ProviderError) as exc:
            last_error = exc
            if attempt >= max_retries:
                logger.error(
                    "llm_retries_exhausted",
                    provider=provider_name,
                    attempts=attempt,
                    error=str(exc),
                )
                raise exc

            delay = calculate_backoff_delay(attempt, base=backoff_base, max_delay=backoff_max)
            logger.warning(
                "llm_retry_backoff",
                provider=provider_name,
                attempt=attempt,
                max_retries=max_retries,
                delay_seconds=delay,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            await asyncio.sleep(delay)
            attempt += 1
        except Exception as exc:
            # Unexpected exceptions
            last_error = exc
            if attempt >= max_retries:
                raise exc
            delay = calculate_backoff_delay(attempt, base=backoff_base, max_delay=backoff_max)
            await asyncio.sleep(delay)
            attempt += 1

    if last_error:
        raise last_error
    raise ProviderError("Execution failed without explicit exception", provider=provider_name)
