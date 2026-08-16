"""Tests for StartupAdapter with pagination and API mocks."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.crawlers.models import CrawlResult
from src.crawlers.startups.adapter import StartupAdapter


@pytest.mark.asyncio
async def test_startup_adapter_discovery():
    mock_client = MagicMock()

    api_response = {
        "items": [
            {"login": "org1", "html_url": "https://github.com/org1"},
            {"login": "org2", "html_url": "https://github.com/org2"},
        ]
    }
    crawl_result = CrawlResult(
        url="https://api.github.com/search/users?q=type:org",
        status_code=200,
        content=json.dumps(api_response),
        success=True,
    )
    mock_client.fetch = AsyncMock(return_value=crawl_result)

    adapter = StartupAdapter(client=mock_client)
    startups = await adapter.discover_startups(limit=2)

    assert len(startups) == 2
    assert startups[0].entity_name == "org1"
    assert startups[1].entity_name == "org2"


@pytest.mark.asyncio
async def test_startup_adapter_pagination():
    mock_client = MagicMock()

    page1_response = {
        "items": [
            {"login": f"org_{i}", "html_url": f"https://github.com/org_{i}"}
            for i in range(5)
        ]
    }
    page2_response = {
        "items": [
            {"login": f"org_{i}", "html_url": f"https://github.com/org_{i}"}
            for i in range(5, 10)
        ]
    }

    mock_client.fetch = AsyncMock(
        side_effect=[
            CrawlResult(url="url1", status_code=200, content=json.dumps(page1_response), success=True),
            CrawlResult(url="url2", status_code=200, content=json.dumps(page2_response), success=True),
        ]
    )

    adapter = StartupAdapter(client=mock_client)
    startups = await adapter.discover_startups(limit=8)

    assert len(startups) == 8
    assert mock_client.fetch.call_count == 2
