"""Tests for concurrency bounds and performance characteristics."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.crawlers.client import AsyncHttpClient


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _client(**kw) -> AsyncHttpClient:
    defaults = dict(concurrency=3, timeout=5, max_retries=1, backoff_base=0.01, backoff_max=0.02)
    defaults.update(kw)
    return AsyncHttpClient(**defaults)


def _mock_response(status=200, body="ok", content_type="text/html"):
    resp = AsyncMock()
    resp.status = status
    resp.content_type = content_type
    resp.text = AsyncMock(return_value=body)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


@pytest.mark.asyncio
async def test_concurrency_limit():
    """Verify that no more than `concurrency` requests are in-flight at once."""
    concurrency = 3
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    def _tracking_get(url, **kwargs):
        """Returns an async context manager that tracks concurrency."""
        nonlocal in_flight, max_in_flight

        async def _aenter(self_cm):
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                if in_flight > max_in_flight:
                    max_in_flight = in_flight
            await asyncio.sleep(0.02)  # Simulate work
            resp = AsyncMock()
            resp.status = 200
            resp.content_type = "text/html"
            resp.text = AsyncMock(return_value="ok")
            return resp

        async def _aexit(self_cm, *args):
            nonlocal in_flight
            async with lock:
                in_flight -= 1

        cm = AsyncMock()
        cm.__aenter__ = _aenter
        cm.__aexit__ = _aexit
        return cm

    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.get = MagicMock(side_effect=_tracking_get)
    session.close = AsyncMock()

    urls = [f"https://example.com/{i}" for i in range(10)]
    client = _client(concurrency=concurrency)
    client._session = session

    results = await client.fetch_many(urls)
    await client.close()

    assert len(results) == 10
    assert all(r.success for r in results)
    assert max_in_flight <= concurrency


@pytest.mark.asyncio
async def test_all_requests_complete():
    """All 20 URLs must complete even with bounded concurrency."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False

    def _get(url, **kwargs):
        return _mock_response(200)

    session.get = MagicMock(side_effect=_get)
    session.close = AsyncMock()

    urls = [f"https://example.com/{i}" for i in range(20)]
    client = _client(concurrency=5)
    client._session = session

    results = await client.fetch_many(urls)
    await client.close()

    assert len(results) == 20
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_failures_do_not_crash_batch():
    """Mixed success/failure with bounded concurrency."""
    call_count = 0

    def _get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count % 3 == 0:
            return _mock_response(500)
        return _mock_response(200)

    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.get = MagicMock(side_effect=_get)
    session.close = AsyncMock()

    urls = [f"https://example.com/{i}" for i in range(10)]
    client = _client(concurrency=3)
    client._session = session

    results = await client.fetch_many(urls)
    await client.close()

    assert len(results) == 10
    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    assert succeeded > 0
    assert failed > 0


@pytest.mark.asyncio
async def test_throughput_10_urls():
    """10 URLs should complete quickly with concurrency=5."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.get = MagicMock(side_effect=lambda url, **kw: _mock_response(200))
    session.close = AsyncMock()

    urls = [f"https://example.com/{i}" for i in range(10)]
    client = _client(concurrency=5)
    client._session = session

    start = time.monotonic()
    results = await client.fetch_many(urls)
    elapsed = time.monotonic() - start
    await client.close()

    assert len(results) == 10
    assert all(r.success for r in results)
    assert elapsed < 5.0


@pytest.mark.asyncio
async def test_throughput_50_urls():
    """50 URLs with concurrency=10 should complete quickly."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    session.get = MagicMock(side_effect=lambda url, **kw: _mock_response(200))
    session.close = AsyncMock()

    urls = [f"https://example.com/{i}" for i in range(50)]
    client = _client(concurrency=10)
    client._session = session

    start = time.monotonic()
    results = await client.fetch_many(urls)
    elapsed = time.monotonic() - start
    await client.close()

    assert len(results) == 50
    assert all(r.success for r in results)
    assert elapsed < 5.0
