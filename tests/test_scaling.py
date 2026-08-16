"""Unit and integration tests for Phase 9 — Production Scaling, Deduplication and Resumable Ingestion."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.storage.checkpoints import Checkpoint, CheckpointRepository
from src.crawlers.rate_limiter import SourceRateLimiter
from src.entity.blocking import generate_blocking_keys, filter_candidates_with_blocking
from src.entity.models import CanonicalEntity
from src.models.enums import MatchMethod
from src.entity.resolver import EntityResolver
from src.storage.repositories.research import ResearchPaperRepository
from src.storage.repositories.news import NewsRepository
from src.storage.repositories.jobs import JobRepository
from src.models.research_paper import ResearchPaper
from src.models.news import News
from src.models.job import Job


# ----------------------------------------------------------------------
# 1. Checkpoint Tests
# ----------------------------------------------------------------------


def test_checkpoint_model():
    cp = Checkpoint(
        vertical="research",
        source="arXiv",
        cursor=50,
        processed_count=50,
        inserted_count=45,
        duplicate_count=5,
        invalid_count=0,
        failed_count=0,
        status="running",
    )
    d = cp.to_dict()
    assert d["vertical"] == "research"
    assert d["cursor"] == 50
    assert d["status"] == "running"

    cp2 = Checkpoint.from_dict(d)
    assert cp2.vertical == "research"
    assert cp2.inserted_count == 45


def test_checkpoint_repository_mock():
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_col
    mock_col.find_one.return_value = {
        "vertical": "research",
        "source": "arXiv",
        "cursor": 100,
        "processed_count": 100,
        "inserted_count": 90,
        "duplicate_count": 10,
        "invalid_count": 0,
        "failed_count": 0,
        "status": "running",
    }

    repo = CheckpointRepository(client=mock_client)
    cp = repo.get_checkpoint("research", "arXiv")
    assert cp is not None
    assert cp.cursor == 100
    assert cp.inserted_count == 90

    repo.save_checkpoint(cp)
    assert mock_col.update_one.called


# ----------------------------------------------------------------------
# 2. Rate Limiter Tests
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_rate_limiter():
    limiter = SourceRateLimiter(requests_per_minute=1200)
    t0 = time.monotonic()
    await limiter.acquire("http://export.arxiv.org/api/query")
    await limiter.acquire("http://export.arxiv.org/api/query")
    t1 = time.monotonic()
    assert (t1 - t0) >= 0.04


# ----------------------------------------------------------------------
# 3. Candidate Blocking Tests
# ----------------------------------------------------------------------


def test_candidate_blocker():
    keys = generate_blocking_keys("OpenAI Inc.")
    assert any("openai" in k for k in keys)

    c1 = CanonicalEntity(canonical_id="1", canonical_name="OpenAI", entity_type="COMPANY")
    c2 = CanonicalEntity(canonical_id="2", canonical_name="Google Research", entity_type="COMPANY")
    c3 = CanonicalEntity(canonical_id="3", canonical_name="OpenAI, Inc.", entity_type="COMPANY")
    c4 = CanonicalEntity(canonical_id="4", canonical_name="Microsoft", entity_type="COMPANY")

    candidates = [c1, c2, c3, c4]
    filtered = filter_candidates_with_blocking("OpenAI", candidates)
    candidate_names = [c.canonical_name for c in filtered]
    assert "OpenAI" in candidate_names
    assert "OpenAI, Inc." in candidate_names
    assert "Google Research" not in candidate_names


# ----------------------------------------------------------------------
# 4. Entity Resolver Caching & Exception Handling Tests
# ----------------------------------------------------------------------


def test_entity_resolver_caching():
    resolver = EntityResolver()
    # Mocking matcher
    resolver.matcher = MagicMock()
    mock_res = MagicMock()
    mock_res.canonical_id = "ent_123"
    mock_res.canonical_name = "OpenAI"
    mock_res.match_method = MatchMethod.EXACT
    mock_res.confidence = 1.0
    resolver.matcher.match.return_value = mock_res
    resolver.repository = MagicMock()
    resolver.repository.get_mapping_by_raw_name.return_value = None
    resolver.repository.get_all_canonical_entities.return_value = []

    # First call
    res1 = resolver.resolve_entity("OpenAI_Test_Unique_123", "http://openai.com", "COMPANY")
    assert res1.canonical_id == "ent_123"

    # Second call should hit in-memory cache
    res2 = resolver.resolve_entity("OpenAI_Test_Unique_123", "http://openai.com", "COMPANY")
    assert res2.canonical_id == "ent_123"


# ----------------------------------------------------------------------
# 5. Repository Batch Insertion Tests
# ----------------------------------------------------------------------


def test_research_repository_save_batch():
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_col
    mock_col.find.return_value = []

    mock_insert_res = MagicMock()
    mock_insert_res.inserted_ids = ["id1", "id2"]
    mock_col.insert_many.return_value = mock_insert_res

    repo = ResearchPaperRepository(client=mock_client)

    now = datetime.now(timezone.utc)
    paper1 = ResearchPaper(
        content={
            "title": "Test Paper 1",
            "authors": ["Author A"],
            "paper_url": "https://arxiv.org/abs/2101.00001",
            "published_date": now,
        },
        collectedAt=now,
    )
    paper2 = ResearchPaper(
        content={
            "title": "Test Paper 2",
            "authors": ["Author B"],
            "paper_url": "https://arxiv.org/abs/2101.00002",
            "published_date": now,
        },
        collectedAt=now,
    )

    # Dry run test
    ins, dup = repo.save_batch([paper1, paper2], dry_run=True)
    assert ins == 2
    assert dup == 0
    assert not mock_col.insert_many.called

    # Real run test
    ins, dup = repo.save_batch([paper1, paper2], dry_run=False)
    assert ins == 2
    assert dup == 0
    assert mock_col.insert_many.called
