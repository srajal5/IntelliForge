"""Tests for retry logic and backoff computation."""

from src.crawlers.retry import (
    compute_backoff,
    is_permanent_error,
    is_retryable_status,
)


# ------------------------------------------------------------------
# is_retryable_status
# ------------------------------------------------------------------


def test_retryable_429():
    assert is_retryable_status(429) is True


def test_retryable_500():
    assert is_retryable_status(500) is True


def test_retryable_502():
    assert is_retryable_status(502) is True


def test_retryable_503():
    assert is_retryable_status(503) is True


def test_retryable_504():
    assert is_retryable_status(504) is True


def test_retryable_none_status():
    """None (timeout / connection failure) is retryable."""
    assert is_retryable_status(None) is True


def test_not_retryable_200():
    assert is_retryable_status(200) is False


def test_not_retryable_301():
    assert is_retryable_status(301) is False


def test_not_retryable_404():
    assert is_retryable_status(404) is False


def test_not_retryable_403():
    assert is_retryable_status(403) is False


# ------------------------------------------------------------------
# is_permanent_error
# ------------------------------------------------------------------


def test_permanent_404():
    assert is_permanent_error(404) is True


def test_permanent_403():
    assert is_permanent_error(403) is True


def test_permanent_401():
    assert is_permanent_error(401) is True


def test_not_permanent_200():
    assert is_permanent_error(200) is False


def test_not_permanent_429():
    assert is_permanent_error(429) is False


def test_not_permanent_500():
    assert is_permanent_error(500) is False


def test_not_permanent_none():
    assert is_permanent_error(None) is False


# ------------------------------------------------------------------
# compute_backoff
# ------------------------------------------------------------------


def test_backoff_attempt_1_no_jitter():
    delay = compute_backoff(1, backoff_base=2.0, jitter=False)
    assert delay == 2.0


def test_backoff_attempt_2_no_jitter():
    delay = compute_backoff(2, backoff_base=2.0, jitter=False)
    assert delay == 4.0


def test_backoff_attempt_3_no_jitter():
    delay = compute_backoff(3, backoff_base=2.0, jitter=False)
    assert delay == 8.0


def test_backoff_respects_max():
    delay = compute_backoff(10, backoff_base=2.0, backoff_max=30.0, jitter=False)
    assert delay == 30.0


def test_backoff_with_jitter():
    delay = compute_backoff(3, backoff_base=2.0, backoff_max=60.0, jitter=True)
    assert 0.0 <= delay <= 8.0


def test_backoff_jitter_bounded():
    """100 samples should all be within [0, max_delay]."""
    for _ in range(100):
        delay = compute_backoff(2, backoff_base=2.0, backoff_max=60.0, jitter=True)
        assert 0.0 <= delay <= 4.0
