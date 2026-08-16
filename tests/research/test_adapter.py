"""Tests for ResearchAdapter (arXiv API pagination and paper discovery)."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from src.crawlers.client import AsyncHttpClient
from src.crawlers.models import CrawlResult
from src.crawlers.research.adapter import ResearchAdapter
from tests.research.test_parser import SAMPLE_ATOM_XML


@pytest.mark.asyncio
async def test_discover_papers_pagination():
    client = MagicMock(spec=AsyncHttpClient)
    client.fetch = AsyncMock(
        return_value=CrawlResult(
            url="http://export.arxiv.org/api/query",
            status_code=200,
            content=SAMPLE_ATOM_XML,
            success=True,
        )
    )

    adapter = ResearchAdapter(client=client)
    # Mock github star fetcher so it doesn't make extra network calls during adapter tests
    adapter.github_fetcher.fetch_stars = AsyncMock(return_value=("https://github.com/microsoft/Swin-Transformer", 5000))

    papers = await adapter.discover_papers(limit=2, enrich_github=True)

    assert len(papers) == 2
    assert papers[0].title == "Swin Transformer: Hierarchical Vision Transformer using Shifted Windows"
    assert papers[0].github_url == "https://github.com/microsoft/Swin-Transformer"
    assert papers[0].github_stars == 5000
    assert papers[1].title == "Attention Is All You Need"
    await adapter.close()


@pytest.mark.asyncio
async def test_discover_papers_http_failure():
    client = MagicMock(spec=AsyncHttpClient)
    client.fetch = AsyncMock(
        return_value=CrawlResult(
            url="http://export.arxiv.org/api/query",
            status_code=500,
            content="",
            success=False,
            error="Server error",
        )
    )

    adapter = ResearchAdapter(client=client)
    papers = await adapter.discover_papers(limit=5)

    assert papers == []
    await adapter.close()


@pytest.mark.asyncio
async def test_query_url_builder():
    url = ResearchAdapter._build_query_url(query="cat:cs.AI", start=10, max_results=20)
    assert "export.arxiv.org/api/query" in url
    assert "start=10" in url
    assert "max_results=20" in url
    assert "search_query=cat%3Acs.AI" in url or "search_query=cat" in url
