"""Tests for AsyncHttpClient — single-URL fetch, retries, error handling.

Uses unittest.mock to mock aiohttp.ClientSession at the method level,
avoiding the aioresponses/aiohttp version incompatibility.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.crawlers.client import AsyncHttpClient


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _client(**kw) -> AsyncHttpClient:
    """Create a client with fast defaults for testing."""
    defaults = dict(
        concurrency=5,
        timeout=5,
        max_retries=3,
        backoff_base=0.01,
        backoff_max=0.05,
    )
    defaults.update(kw)
    return AsyncHttpClient(**defaults)


def _mock_response(status=200, body="ok", content_type="text/html", headers=None):
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.content_type = content_type
    resp.headers = headers if headers is not None else {}
    resp.text = AsyncMock(return_value=body)
    # Make it work as an async context manager
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _mock_session(responses):
    """Create a mock session that returns responses in order.

    *responses* is a list of mock-response objects or exceptions.
    Each call to session.get() pops the next item from the list.
    """
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False

    call_count = 0

    def _get(url, **kwargs):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        item = responses[idx]
        if isinstance(item, Exception):
            raise item
        return item

    session.get = MagicMock(side_effect=_get)

    async def _close():
        session.closed = True

    session.close = AsyncMock(side_effect=_close)
    return session


# ------------------------------------------------------------------
# Successful request
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_success():
    resp = _mock_response(200, "hello world")
    client = _client()
    client._session = _mock_session([resp])

    result = await client.fetch("https://example.com")

    assert result.success is True
    assert result.status_code == 200
    assert result.content == "hello world"
    assert result.attempts == 1
    assert result.response_time >= 0.0
    assert result.error is None
    await client.close()


@pytest.mark.asyncio
async def test_fetch_response_headers():
    resp = _mock_response(200, "data", content_type="application/json")
    client = _client()
    client._session = _mock_session([resp])

    result = await client.fetch("https://example.com")

    assert result.content_type == "application/json"
    await client.close()


# ------------------------------------------------------------------
# Timeout
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_timeout():
    timeout_err = asyncio.TimeoutError()
    client = _client()
    client._session = _mock_session([timeout_err, timeout_err, timeout_err])

    result = await client.fetch("https://example.com")

    assert result.success is False
    assert result.status_code is None
    assert "Timeout" in (result.error or "")
    assert result.attempts == 3
    await client.close()


# ------------------------------------------------------------------
# Connection failure
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_connection_error():
    conn_err = aiohttp.ClientConnectorError(
        connection_key=MagicMock(), os_error=OSError("refused")
    )
    client = _client()
    client._session = _mock_session([conn_err, conn_err, conn_err])

    result = await client.fetch("https://example.com")

    assert result.success is False
    assert result.attempts == 3
    assert "Connection error" in (result.error or "")
    await client.close()


# ------------------------------------------------------------------
# 429 retry (rate limit)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_429_then_success():
    """429 → 429 → 200: retries and eventually succeeds."""
    r429 = _mock_response(429, "rate limited")
    r200 = _mock_response(200, "ok")
    client = _client()
    client._session = _mock_session([r429, r429, r200])

    result = await client.fetch("https://example.com")

    assert result.success is True
    assert result.status_code == 200
    assert result.attempts == 3
    await client.close()


# ------------------------------------------------------------------
# 500 / 503 retry
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_500_then_success():
    """500 → 503 → 200: retries transient server errors."""
    r500 = _mock_response(500, "error")
    r503 = _mock_response(503, "unavailable")
    r200 = _mock_response(200, "recovered")
    client = _client()
    client._session = _mock_session([r500, r503, r200])

    result = await client.fetch("https://example.com")

    assert result.success is True
    assert result.status_code == 200
    assert result.attempts == 3
    await client.close()


@pytest.mark.asyncio
async def test_fetch_503_exhausted():
    """503 × 3: all retries exhausted → failure."""
    r503 = _mock_response(503, "unavailable")
    client = _client()
    client._session = _mock_session([r503, r503, r503])

    result = await client.fetch("https://example.com")

    assert result.success is False
    assert result.status_code == 503
    assert result.attempts == 3
    await client.close()


# ------------------------------------------------------------------
# 404 — permanent, no retry
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_404_no_retry():
    """404 is permanent and must not be retried."""
    r404 = _mock_response(404, "Not Found")
    client = _client()
    client._session = _mock_session([r404])

    result = await client.fetch("https://example.com/missing")

    assert result.success is False
    assert result.status_code == 404
    assert result.attempts == 1
    await client.close()


@pytest.mark.asyncio
async def test_fetch_403_no_retry():
    """403 is permanent and must not be retried."""
    r403 = _mock_response(403, "Forbidden")
    client = _client()
    client._session = _mock_session([r403])

    result = await client.fetch("https://example.com/secret")

    assert result.success is False
    assert result.status_code == 403
    assert result.attempts == 1
    await client.close()


# ------------------------------------------------------------------
# Session cleanup
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_closed_after_context_manager():
    resp = _mock_response(200, "hi")
    client = _client()
    client._session = _mock_session([resp])

    async with client:
        await client.fetch("https://example.com")

    assert client._session is None


@pytest.mark.asyncio
async def test_close_idempotent():
    """Calling close() multiple times must not raise."""
    client = _client()
    await client.close()
    await client.close()


# ------------------------------------------------------------------
# Configuration defaults
# ------------------------------------------------------------------


def test_default_concurrency():
    c = AsyncHttpClient()
    assert c._concurrency == 10


def test_default_timeout():
    c = AsyncHttpClient()
    assert c._timeout == 30


def test_default_max_retries():
    c = AsyncHttpClient()
    assert c._max_retries == 3


def test_custom_configuration():
    c = AsyncHttpClient(concurrency=20, timeout=60, max_retries=5)
    assert c._concurrency == 20
    assert c._timeout == 60
    assert c._max_retries == 5


def test_from_settings():
    """from_settings reads config from a Settings-like object."""

    class FakeSettings:
        crawler_concurrency = 15
        crawler_timeout = 45
        crawler_max_retries = 4
        crawler_backoff_base = 3.0
        crawler_backoff_max = 90.0
        crawler_user_agent = "TestBot/1.0"

    c = AsyncHttpClient.from_settings(FakeSettings())
    assert c._concurrency == 15
    assert c._timeout == 45
    assert c._max_retries == 4


# ------------------------------------------------------------------
# Response parsing
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_content_preserved():
    html = "<html><body><h1>Title</h1></body></html>"
    resp = _mock_response(200, html)
    client = _client()
    client._session = _mock_session([resp])

    result = await client.fetch("https://example.com")

    assert result.content == html
    await client.close()


@pytest.mark.asyncio
async def test_structured_result_fields():
    resp = _mock_response(200, "x")
    client = _client()
    client._session = _mock_session([resp])

    result = await client.fetch("https://example.com")

    assert result.url == "https://example.com"
    assert result.fetched_at is not None
    assert result.content_length == 1
    await client.close()
