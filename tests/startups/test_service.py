"""Tests for StartupsService orchestration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.crawlers.startups.models import RawStartup
from src.services.startups import StartupsService


@pytest.mark.asyncio
async def test_startups_service_ingest_orchestration():
    mock_settings = MagicMock()
    mock_settings.mongodb_uri = "mongodb://localhost:27017"
    mock_settings.mongodb_database = "test_db"

    raw_startups = [
        RawStartup("OpenAI", "https://github.com/openai", "GitHub Organizations", 500),
        RawStartup("Anthropic", "https://github.com/anthropic", "GitHub Organizations", None),
    ]

    with patch("src.services.startups.StartupAdapter") as mock_adapter_cls, \
         patch("src.services.startups.StartupRepository") as mock_repo_cls:

        mock_adapter = MagicMock()
        mock_adapter.discover_startups = AsyncMock(return_value=raw_startups)
        mock_adapter.close = AsyncMock()
        mock_adapter_cls.return_value = mock_adapter

        mock_repo = MagicMock()
        mock_repo.save_batch.return_value = (2, 0)
        mock_repo.close = MagicMock()
        mock_repo_cls.return_value = mock_repo

        service = StartupsService(settings=mock_settings)
        result = await service.ingest(limit=2)

        assert result["status"] == "success"
        assert result["discovered"] == 2
        assert result["valid"] == 2
        assert result["inserted"] == 2
        assert result["duplicates"] == 0
        assert result["invalid"] == 0
