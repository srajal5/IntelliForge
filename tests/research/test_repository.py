"""Tests for ResearchPaperRepository MongoDB storage and deduplication."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from src.models.research_paper import ResearchPaper
from src.storage.repositories.research import ResearchPaperRepository


def _make_paper(title="Attention Is All You Need", paper_url="https://arxiv.org/abs/1706.03762") -> ResearchPaper:
    return ResearchPaper(
        content={
            "title": title,
            "authors": ["Vaswani, A."],
            "paper_url": paper_url,
            "github_url": "https://github.com/tensorflow/tensor2tensor",
            "github_stars": 15000,
            "published_date": datetime(2017, 6, 12, tzinfo=timezone.utc),
        },
        collectedAt=datetime.now(timezone.utc),
    )


def test_repository_save_and_deduplicate():
    # Mock PyMongo collection
    mock_col = MagicMock()
    mock_col.count_documents.side_effect = [0, 1]  # First time not found, second time found
    mock_col.insert_one = MagicMock()

    mock_db = {"research_papers": mock_col}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    repo = ResearchPaperRepository(client=mock_client)
    paper = _make_paper()

    # First save: inserted
    result1 = repo.save(paper)
    assert result1 is True
    assert mock_col.insert_one.call_count == 1

    # Second save: duplicate, skipped
    result2 = repo.save(paper)
    assert result2 is False
    assert mock_col.insert_one.call_count == 1  # Not inserted again


def test_repository_setup_indexes():
    mock_col = MagicMock()
    mock_db = {"research_papers": mock_col}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    repo = ResearchPaperRepository(client=mock_client)
    repo.setup_indexes()

    assert mock_col.create_index.call_count >= 2
