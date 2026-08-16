"""Tests for batch crawling (fetch_many)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.crawlers.client import AsyncHttpClient


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _client(**kw) -> AsyncHttpClient:
    defaults = dict(concurrency=5, timeout=5, max_retries=2, backoff_base=0.01, backoff_max=0.02)
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


def _mock_session_for_urls(url_responses: dict[str, list]):
    """Create a mock session that maps URLs to response sequences.

    url_responses: {url: [resp1, resp2, ...]}
    Each call to session.get(url) pops the next response for that URL.
    """
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    counters: dict[str, int] = {}

    def _get(url, **kwargs):
        url_str = str(url)
        idx = counters.get(url_str, 0)
        counters[url_str] = idx + 1
        resps = url_responses.get(url_str, [_mock_response(200)])
        item = resps[min(idx, len(resps) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    session.get = MagicMock(side_effect=_get)
    session.close = AsyncMock()
    return session


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_all_succeed():
    urls = [f"https://example.com/{i}" for i in range(5)]
    url_map = {u: [_mock_response(200, f"body {u}")] for u in urls}

    client = _client()
    client._session = _mock_session_for_urls(url_map)

    results = await client.fetch_many(urls)
    await client.close()

    assert len(results) == 5
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_batch_preserves_order():
    urls = [f"https://example.com/{i}" for i in range(3)]
    url_map = {u: [_mock_response(200)] for u in urls}

    client = _client()
    client._session = _mock_session_for_urls(url_map)

    results = await client.fetch_many(urls)
    await client.close()

    for i, result in enumerate(results):
        assert result.url == urls[i]


@pytest.mark.asyncio
async def test_batch_partial_failure():
    """One failing URL must not crash the entire batch."""
    urls = ["https://example.com/ok1", "https://example.com/fail", "https://example.com/ok2"]
    url_map = {
        urls[0]: [_mock_response(200)],
        urls[1]: [_mock_response(404, "Not Found")],
        urls[2]: [_mock_response(200)],
    }

    client = _client()
    client._session = _mock_session_for_urls(url_map)

    results = await client.fetch_many(urls)
    await client.close()

    assert len(results) == 3
    assert results[0].success is True
    assert results[1].success is False
    assert results[1].status_code == 404
    assert results[2].success is True


@pytest.mark.asyncio
async def test_batch_all_fail():
    urls = [f"https://example.com/{i}" for i in range(3)]
    url_map = {u: [_mock_response(500), _mock_response(500)] for u in urls}

    client = _client()
    client._session = _mock_session_for_urls(url_map)

    results = await client.fetch_many(urls)
    await client.close()

    assert len(results) == 3
    assert all(not r.success for r in results)


@pytest.mark.asyncio
async def test_batch_empty_urls():
    client = _client()
    results = await client.fetch_many([])
    await client.close()
    assert results == []


@pytest.mark.asyncio
async def test_batch_single_url():
    url_map = {"https://example.com": [_mock_response(200, "solo")]}

    client = _client()
    client._session = _mock_session_for_urls(url_map)

    results = await client.fetch_many(["https://example.com"])
    await client.close()

    assert len(results) == 1
    assert results[0].success is True


@pytest.mark.asyncio
async def test_batch_error_info():
    """Failed results must carry structured error information."""
    url_map = {"https://example.com": [_mock_response(503, "unavail")]}

    client = _client(max_retries=1)
    client._session = _mock_session_for_urls(url_map)

    results = await client.fetch_many(["https://example.com"])
    await client.close()

    assert len(results) == 1
    assert results[0].error is not None
    assert "503" in results[0].error
