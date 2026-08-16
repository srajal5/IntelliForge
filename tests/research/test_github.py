"""Tests for GitHub repository discovery and star metadata fetcher."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.crawlers.client import AsyncHttpClient
from src.crawlers.models import CrawlResult
from src.crawlers.research.github import GitHubDiscoverer, GitHubMetadataFetcher


def test_discover_valid_github_url():
    text = "We release our official code at https://github.com/microsoft/Swin-Transformer for reproducibility."
    url = GitHubDiscoverer.discover_github_url(text)
    assert url == "https://github.com/microsoft/Swin-Transformer"


def test_discover_github_url_with_trailing_punctuation():
    text = "Check out the repo (https://github.com/huggingface/transformers.git)."
    url = GitHubDiscoverer.discover_github_url(text)
    assert url == "https://github.com/huggingface/transformers"


def test_discover_no_github_url():
    text = "This paper introduces a novel transformer model without public code."
    url = GitHubDiscoverer.discover_github_url(text)
    assert url is None


def test_discover_non_repo_paths_ignored():
    text = "Join discussions on https://github.com/sponsors or https://github.com/topics."
    url = GitHubDiscoverer.discover_github_url(text)
    assert url is None


@pytest.mark.asyncio
async def test_fetch_stars_success():
    client = MagicMock(spec=AsyncHttpClient)
    payload = json.dumps({"stargazers_count": 12500})
    client.fetch = AsyncMock(
        return_value=CrawlResult(
            url="https://api.github.com/repos/microsoft/Swin-Transformer",
            status_code=200,
            content=payload,
            success=True,
        )
    )

    fetcher = GitHubMetadataFetcher(client=client)
    url, stars = await fetcher.fetch_stars("https://github.com/microsoft/Swin-Transformer")

    assert url == "https://github.com/microsoft/Swin-Transformer"
    assert stars == 12500


@pytest.mark.asyncio
async def test_fetch_stars_404_repo_not_found():
    client = MagicMock(spec=AsyncHttpClient)
    client.fetch = AsyncMock(
        return_value=CrawlResult(
            url="https://api.github.com/repos/user/nonexistent",
            status_code=404,
            content="Not Found",
            success=False,
        )
    )

    fetcher = GitHubMetadataFetcher(client=client)
    url, stars = await fetcher.fetch_stars("https://github.com/user/nonexistent")

    assert url is None
    assert stars is None


@pytest.mark.asyncio
async def test_fetch_stars_api_rate_limit_or_error():
    client = MagicMock(spec=AsyncHttpClient)
    client.fetch = AsyncMock(
        return_value=CrawlResult(
            url="https://api.github.com/repos/user/repo",
            status_code=403,
            content="Rate limit exceeded",
            success=False,
            error="403 Forbidden",
        )
    )

    fetcher = GitHubMetadataFetcher(client=client)
    url, stars = await fetcher.fetch_stars("https://github.com/user/repo")

    # Preserves URL, returns None for stars
    assert url == "https://github.com/user/repo"
    assert stars is None


@pytest.mark.asyncio
async def test_fetch_stars_empty_url():
    fetcher = GitHubMetadataFetcher()
    url, stars = await fetcher.fetch_stars("")
    assert url is None
    assert stars is None
