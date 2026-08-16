"""Tests for ProductsService orchestration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.crawlers.products.models import RawProduct
from src.models.enums import PricingModel
from src.services.products import ProductsService


@pytest.mark.asyncio
async def test_products_service_ingest_orchestration():
    mock_settings = MagicMock()
    mock_settings.mongodb_uri = "mongodb://localhost:27017"
    mock_settings.mongodb_database = "test_db"

    raw_products = [
        RawProduct("n8n", "n8n-io", "https://github.com/n8n-io/n8n", "GitHub Products", PricingModel.FREE),
        RawProduct("AutoGPT", "Significant-Gravitas", "https://github.com/Significant-Gravitas/AutoGPT", "GitHub Products", None),
    ]

    with patch("src.services.products.ProductAdapter") as mock_adapter_cls, \
         patch("src.services.products.ProductRepository") as mock_repo_cls:

        mock_adapter = MagicMock()
        mock_adapter.discover_products = AsyncMock(return_value=raw_products)
        mock_adapter.close = AsyncMock()
        mock_adapter_cls.return_value = mock_adapter

        mock_repo = MagicMock()
        mock_repo.save_batch.return_value = (2, 0)
        mock_repo.close = MagicMock()
        mock_repo_cls.return_value = mock_repo

        service = ProductsService(settings=mock_settings)
        result = await service.ingest(limit=2)

        assert result["status"] == "success"
        assert result["discovered"] == 2
        assert result["valid"] == 2
        assert result["inserted"] == 2
        assert result["duplicates"] == 0
        assert result["invalid"] == 0
