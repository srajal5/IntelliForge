"""Unit tests for retry logic and exponential backoff calculations."""

import pytest
from unittest.mock import AsyncMock

from src.llm.retry import calculate_backoff_delay, execute_with_retry
from src.llm.exceptions import (
    AuthenticationError,
    OversizedRequestError,
    RateLimitError,
    ProviderError,
)


def test_calculate_backoff_delay():
    d1 = calculate_backoff_delay(attempt=1, base=2.0, max_delay=30.0)
    assert 1.0 <= d1 <= 1.5

    d2 = calculate_backoff_delay(attempt=3, base=2.0, max_delay=30.0)
    assert 4.0 <= d2 <= 6.0

    d_max = calculate_backoff_delay(attempt=10, base=2.0, max_delay=10.0)
    assert 10.0 <= d_max <= 15.0


@pytest.mark.asyncio
async def test_execute_with_retry_success_after_retry():
    mock_coro = AsyncMock()
    mock_coro.side_effect = [
        RateLimitError("429 rate limit", provider="test"),
        "success_result",
    ]

    result = await execute_with_retry(
        coro_fn=mock_coro,
        provider_name="test",
        max_retries=2,
        backoff_base=0.01,
    )

    assert result == "success_result"
    assert mock_coro.call_count == 2


@pytest.mark.asyncio
async def test_execute_with_retry_no_retry_on_auth_error():
    mock_coro = AsyncMock()
    mock_coro.side_effect = AuthenticationError("401 Unauthorized", provider="test")

    with pytest.raises(AuthenticationError):
        await execute_with_retry(
            coro_fn=mock_coro,
            provider_name="test",
            max_retries=3,
            backoff_base=0.01,
        )

    # Must fail immediately without retrying
    assert mock_coro.call_count == 1
