"""Tests for ProductAdapter with pagination and API mocks."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.crawlers.models import CrawlResult
from src.crawlers.products.adapter import ProductAdapter


@pytest.mark.asyncio
async def test_product_adapter_discovery():
    mock_client = MagicMock()

    api_response = {
        "items": [
            {
                "name": "p1",
                "owner": {"login": "o1"},
                "html_url": "https://github.com/o1/p1",
                "license": {"key": "mit"},
            },
            {
                "name": "p2",
                "owner": {"login": "o2"},
                "html_url": "https://github.com/o2/p2",
                "license": {"key": "apache-2.0"},
            },
        ]
    }
    crawl_result = CrawlResult(
        url="https://api.github.com/search/repositories",
        status_code=200,
        content=json.dumps(api_response),
        success=True,
    )
    mock_client.fetch = AsyncMock(return_value=crawl_result)

    adapter = ProductAdapter(client=mock_client)
    products = await adapter.discover_products(limit=2)

    assert len(products) == 2
    assert products[0].product_name == "p1"
    assert products[1].product_name == "p2"


@pytest.mark.asyncio
async def test_product_adapter_pagination():
    mock_client = MagicMock()

    page1_response = {
        "items": [
            {
                "name": f"p_{i}",
                "owner": {"login": f"o_{i}"},
                "html_url": f"https://github.com/o_{i}/p_{i}",
            }
            for i in range(5)
        ]
    }
    page2_response = {
        "items": [
            {
                "name": f"p_{i}",
                "owner": {"login": f"o_{i}"},
                "html_url": f"https://github.com/o_{i}/p_{i}",
            }
            for i in range(5, 10)
        ]
    }

    mock_client.fetch = AsyncMock(
        side_effect=[
            CrawlResult(url="url1", status_code=200, content=json.dumps(page1_response), success=True),
            CrawlResult(url="url2", status_code=200, content=json.dumps(page2_response), success=True),
        ]
    )

    adapter = ProductAdapter(client=mock_client)
    products = await adapter.discover_products(limit=8)

    assert len(products) == 8
    assert mock_client.fetch.call_count == 2
