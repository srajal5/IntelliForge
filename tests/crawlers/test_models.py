"""Tests for CrawlResult and CrawlPolicy models."""

import pytest
from pydantic import ValidationError

from src.crawlers.models import CrawlPolicy, CrawlResult


# ------------------------------------------------------------------
# CrawlResult
# ------------------------------------------------------------------


def test_crawl_result_success():
    r = CrawlResult(
        url="https://example.com",
        status_code=200,
        content="<html>hello</html>",
        content_type="text/html",
        response_time=0.42,
        attempts=1,
        success=True,
    )
    assert r.success is True
    assert r.status_code == 200
    assert r.content_length > 0
    assert r.error is None


def test_crawl_result_failure():
    r = CrawlResult(
        url="https://example.com",
        status_code=None,
        response_time=30.0,
        attempts=3,
        success=False,
        error="Timeout",
    )
    assert r.success is False
    assert r.status_code is None
    assert r.content_length == 0


def test_crawl_result_defaults():
    r = CrawlResult(url="https://example.com")
    assert r.success is False
    assert r.attempts == 1
    assert r.response_time == 0.0
    assert r.fetched_at is not None


def test_crawl_result_json_serialization():
    r = CrawlResult(
        url="https://example.com",
        status_code=200,
        content="hello",
        content_type="text/plain",
        response_time=0.1,
        success=True,
    )
    data = r.model_dump(mode="json")
    assert data["url"] == "https://example.com"
    assert data["status_code"] == 200

    json_str = r.model_dump_json()
    assert "example.com" in json_str


def test_crawl_result_content_length():
    r = CrawlResult(url="https://example.com", content="abc", success=True)
    assert r.content_length == 3


def test_crawl_result_content_length_none():
    r = CrawlResult(url="https://example.com")
    assert r.content_length == 0


# ------------------------------------------------------------------
# CrawlPolicy
# ------------------------------------------------------------------


def test_crawl_policy_defaults():
    p = CrawlPolicy()
    assert p.concurrency == 10
    assert p.timeout == 30
    assert p.request_delay == 0.0
    assert p.allowed_domains is None
    assert p.headers == {}


def test_crawl_policy_custom():
    p = CrawlPolicy(
        allowed_domains=["example.com"],
        request_delay=1.0,
        concurrency=5,
        headers={"Accept": "text/html"},
        timeout=15,
    )
    assert p.allowed_domains == ["example.com"]
    assert p.concurrency == 5
    assert p.timeout == 15


def test_crawl_policy_invalid_concurrency():
    with pytest.raises(ValidationError, match="concurrency"):
        CrawlPolicy(concurrency=0)


def test_crawl_policy_invalid_timeout():
    with pytest.raises(ValidationError, match="timeout"):
        CrawlPolicy(timeout=0)


def test_crawl_policy_negative_delay():
    with pytest.raises(ValidationError, match="request_delay"):
        CrawlPolicy(request_delay=-1.0)
