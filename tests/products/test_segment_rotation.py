"""Unit tests for product segment rotation, checkpointing, and cross-segment deduplication."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.crawlers.models import CrawlResult
from src.crawlers.products.sources.github_repos import GitHubReposSource, PRODUCT_TOPIC_QUERIES
from src.crawlers.products.adapter import ProductAdapter
from src.services.products import ProductsService
from src.storage.checkpoints import Checkpoint, CheckpointRepository


@pytest.mark.asyncio
async def test_github_repos_source_segment_rotation():
    """Test that GitHubReposSource automatically advances segment when page limit or 0 items reached."""
    mock_client = MagicMock()

    # Segment 0 page 1: empty items -> should advance to segment 1 page 1
    resp_empty = {"items": []}
    # Segment 1 page 1: 2 items
    resp_items = {
        "items": [
            {"name": f"item_{i}", "owner": {"login": f"user_{i}"}, "html_url": f"https://github.com/user_{i}/item_{i}"}
            for i in range(2)
        ]
    }

    mock_client.fetch = AsyncMock(
        side_effect=[
            CrawlResult(url="url1", status_code=200, content=json.dumps(resp_empty), success=True),
            CrawlResult(url="url2", status_code=200, content=json.dumps(resp_items), success=True),
        ]
    )

    source = GitHubReposSource(client=mock_client)
    discovered, next_seg, next_page, exhausted = await source.discover_segment(
        limit=2, segment=0, page=1, max_pages_per_segment=10
    )

    assert len(discovered) == 2
    assert next_seg == 1
    assert next_page == 2
    assert not exhausted
    assert mock_client.fetch.call_count == 2


@pytest.mark.asyncio
async def test_github_repos_source_exhaustion():
    """Test that source reports exhausted_all when reaching beyond available segments."""
    mock_client = MagicMock()
    mock_client.fetch = AsyncMock(
        return_value=CrawlResult(url="url", status_code=200, content=json.dumps({"items": []}), success=True)
    )

    source = GitHubReposSource(client=mock_client)
    last_segment_index = len(PRODUCT_TOPIC_QUERIES) - 1
    discovered, next_seg, next_page, exhausted = await source.discover_segment(
        limit=5, segment=last_segment_index, page=1, max_pages_per_segment=1
    )

    assert len(discovered) == 0
    assert exhausted


@pytest.mark.asyncio
async def test_product_service_checkpoint_resume_and_rotation():
    """Test that ProductsService resumes from saved segment/cursor and updates checkpoint."""
    mock_settings = MagicMock()
    mock_settings.mongodb_uri = "mongodb://localhost:27017"
    mock_settings.mongodb_database = "test_db"

    saved_cp = Checkpoint(
        vertical="products",
        source="GitHub Search",
        cursor=5,
        segment=2,
        processed_count=100,
        inserted_count=100,
    )

    with patch("src.services.products.ProductAdapter") as mock_adapter_cls, \
         patch("src.services.products.ProductRepository") as mock_repo_cls, \
         patch("src.services.products.CheckpointRepository") as mock_cp_cls:

        mock_adapter = MagicMock()
        # Mock discover_products returning raw products, next segment=2, next page=6
        from src.crawlers.products.models import RawProduct
        from src.models.enums import PricingModel

        raw = RawProduct("TestProd", "Owner", "https://github.com/Owner/TestProd", "GitHub Products", PricingModel.FREE)
        mock_adapter.discover_products = AsyncMock(return_value=([raw], 2, 6, False))
        mock_adapter.close = AsyncMock()
        mock_adapter.source_metrics = {}
        mock_adapter_cls.return_value = mock_adapter

        mock_repo = MagicMock()
        mock_repo.count.side_effect = [100, 101, 101, 101, 101]
        mock_repo.save_batch.return_value = (1, 0)
        mock_repo.close = MagicMock()
        mock_repo_cls.return_value = mock_repo

        mock_cp = MagicMock()
        mock_cp.get_checkpoint.return_value = saved_cp
        mock_cp.close = MagicMock()
        mock_cp_cls.return_value = mock_cp

        service = ProductsService(settings=mock_settings)
        result = await service.ingest(limit=101, resume=True)

        assert result["status"] == "success"
        # Check that discover_products was called starting from segment=2, page=5
        mock_adapter.discover_products.assert_called_with(
            limit=1, segment=2, page=5, return_tuple=True
        )
        assert mock_cp.save_checkpoint.called
        saved_arg = mock_cp.save_checkpoint.call_args[0][0]
        assert saved_arg.segment == 2
        assert saved_arg.cursor == 6
