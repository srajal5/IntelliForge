"""End-to-end tests for ResearchService orchestration."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.crawlers.research.models import RawPaper
from src.services.research import ResearchService


@pytest.mark.asyncio
async def test_research_service_ingestion_success():
    raw_paper = RawPaper(
        title="Attention Is All You Need",
        authors=["Vaswani, A."],
        paper_url="https://arxiv.org/abs/1706.03762",
        summary="Code at https://github.com/tensorflow/tensor2tensor",
        published_date=datetime(2017, 6, 12, tzinfo=timezone.utc),
        github_url="https://github.com/tensorflow/tensor2tensor",
        github_stars=15000,
    )

    mock_settings = MagicMock()
    mock_settings.mongodb_uri = "mongodb://localhost:27017"
    mock_settings.mongodb_database = "test_db"
    mock_settings.github_token = ""

    with patch("src.services.research.ResearchAdapter") as MockAdapter, \
         patch("src.services.research.ResearchPaperRepository") as MockRepo:

        adapter_instance = AsyncMock()
        adapter_instance.discover_papers.return_value = [raw_paper]
        MockAdapter.return_value = adapter_instance

        repo_instance = MagicMock()
        repo_instance.save_batch.return_value = (1, 0)  # Inserted 1, dup 0
        MockRepo.return_value = repo_instance

        service = ResearchService(settings=mock_settings)
        res = await service.ingest(limit=1)

        assert res["status"] == "success"
        assert res["requested"] == 1
        assert res["discovered"] == 1
        assert res["valid"] == 1
        assert res["inserted"] == 1
        assert res["duplicates"] == 0
        assert res["github_count"] == 1
        assert res["github_stars_count"] == 1


@pytest.mark.asyncio
async def test_research_service_idempotent_second_run():
    raw_paper = RawPaper(
        title="Attention Is All You Need",
        authors=["Vaswani, A."],
        paper_url="https://arxiv.org/abs/1706.03762",
        summary="",
        published_date=datetime(2017, 6, 12, tzinfo=timezone.utc),
    )

    mock_settings = MagicMock()

    with patch("src.services.research.ResearchAdapter") as MockAdapter, \
         patch("src.services.research.ResearchPaperRepository") as MockRepo:

        adapter_instance = AsyncMock()
        adapter_instance.discover_papers.return_value = [raw_paper]
        MockAdapter.return_value = adapter_instance

        repo_instance = MagicMock()
        repo_instance.save_batch.return_value = (0, 1)  # Inserted 0, dup 1
        MockRepo.return_value = repo_instance

        service = ResearchService(settings=mock_settings)
        res = await service.ingest(limit=1)

        assert res["status"] == "success"
        assert res["discovered"] == 1
        assert res["inserted"] == 0
        assert res["duplicates"] == 1
