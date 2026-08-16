"""Retry logic with exponential backoff and jitter.

Separates the *decision* to retry (based on HTTP status / error type)
from the *delay computation*, making both independently testable.
"""

from __future__ import annotations

import random

# HTTP status codes that indicate transient / retryable server conditions.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# 4xx codes that are *never* retried (client errors, permanent problems).
PERMANENT_CLIENT_ERRORS: frozenset[int] = frozenset(
    {400, 401, 403, 404, 405, 406, 410, 422}
)


def is_retryable_status(status_code: int | None) -> bool:
    """Return True if the HTTP status warrants a retry."""
    if status_code is None:
        # No response at all (timeout / connection error) → retryable.
        return True
    return status_code in RETRYABLE_STATUS_CODES


def is_permanent_error(status_code: int | None) -> bool:
    """Return True if the status indicates a permanent client error."""
    if status_code is None:
        return False
    return status_code in PERMANENT_CLIENT_ERRORS


def compute_backoff(
    attempt: int,
    backoff_base: float = 2.0,
    backoff_max: float = 60.0,
    jitter: bool = True,
) -> float:
    """Compute the delay before the *next* attempt.

    Uses truncated exponential backoff:
        delay = min(base ^ attempt, max)

    When *jitter* is True a random factor in [0, delay] is returned
    instead of the full delay, reducing thundering-herd effects.

    Parameters
    ----------
    attempt:
        The 1-based attempt number that just failed.
    backoff_base:
        Base of the exponential.
    backoff_max:
        Ceiling for the delay in seconds.
    jitter:
        Add randomised jitter.
    """
    delay = min(backoff_base ** attempt, backoff_max)
    if jitter:
        delay = random.uniform(0, delay)  # noqa: S311  # not for crypto
    return round(delay, 3)
