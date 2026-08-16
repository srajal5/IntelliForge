"""Unit tests for Jobs ingestion vertical (Requirement 24)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.crawlers.jobs.adapter import JobsAdapter
from src.crawlers.jobs.models import RawJobPosting
from src.crawlers.jobs.parser import (
    classify_role_family,
    classify_role_family_deterministic,
    detect_remote_status,
    parse_job_date,
    parse_job_item,
)
from src.crawlers.jobs.qualifier import qualify_job_posting
from src.models.job import Job
from src.services.jobs import JobsService
from src.storage.repositories.jobs import JobRepository

SAMPLE_JOBS_API_RESPONSE = {
    "data": [
        {
            "company_name": "AI Systems Corp",
            "title": "Senior Machine Learning Engineer",
            "url": "https://example.com/jobs/ml-eng",
            "created_at": 1786708800,
            "remote": True,
            "description": "<p>We are seeking a Machine Learning Engineer to build LLM pipelines.</p>",
        },
        {
            "company_name": "CloudOps Solutions",
            "title": "DevOps Lead Engineer",
            "url": "https://example.com/jobs/devops-lead",
            "created_at": "2026-08-15T14:00:00Z",
            "location": "Remote",
            "description": "Lead our cloud infrastructure and Kubernetes cluster.",
        },
        {
            "company_name": "Fintech Global",
            "title": "Full Stack Software Engineer",
            "url": "https://example.com/jobs/fullstack",
            "created_at": "Wed, 15 Aug 2026 12:00:00 +0000",
            "location": "Onsite Only",
            "description": "Onsite software developer position.",
        },
    ]
}


def test_parse_job_item():
    item = SAMPLE_JOBS_API_RESPONSE["data"][0]
    raw = parse_job_item(item)

    assert raw is not None
    assert raw.company == "AI Systems Corp"
    assert raw.title == "Senior Machine Learning Engineer"
    assert raw.url == "https://example.com/jobs/ml-eng"
    assert raw.is_remote is True
    assert raw.role_family == "Data & AI"
    assert raw.description is not None
    assert "Machine Learning Engineer" in raw.description


def test_parse_job_date_formats():
    # Unix timestamp
    dt1 = parse_job_date(1786708800)
    assert dt1.tzinfo is not None

    # ISO string
    dt2 = parse_job_date("2026-08-15T14:00:00Z")
    assert dt2.year == 2026
    assert dt2.month == 8

    # RFC 822 string
    dt3 = parse_job_date("Wed, 15 Aug 2026 12:00:00 +0000")
    assert dt3.year == 2026

    # Invalid fallback
    dt4 = parse_job_date("invalid-date")
    assert isinstance(dt4, datetime)


def test_detect_remote_status():
    # Explicit boolean
    assert detect_remote_status({"remote": True}, "Engineer") is True

    # Location keyword
    assert detect_remote_status({"location": "Remote - US"}, "Engineer") is True

    # Onsite explicit keyword override
    assert detect_remote_status({"location": "Onsite Only"}, "Engineer", "Onsite only required") is False

    # Title keyword
    assert detect_remote_status({}, "Remote Python Developer") is True


def test_classify_role_family_deterministic():
    assert classify_role_family_deterministic("Senior Backend Engineer") == "Engineering"
    assert classify_role_family_deterministic("Data Scientist - AI") == "Data & AI"
    assert classify_role_family_deterministic("SRE / DevOps Manager") == "Infrastructure"
    assert classify_role_family_deterministic("Cybersecurity Analyst") == "Security"
    assert classify_role_family_deterministic("QA Lead Engineer") == "Quality Assurance"
    assert classify_role_family_deterministic("Senior Product Manager") == "Product & Design"
    assert classify_role_family_deterministic("Unknown Specialist") is None


@pytest.mark.asyncio
async def test_classify_role_family_with_llm():
    # 1. Deterministic hit -> returns Engineering without calling LLM
    mock_orchestrator = AsyncMock()
    res1 = await classify_role_family("Software Developer", orchestrator=mock_orchestrator)
    assert res1 == "Engineering"
    mock_orchestrator.generate.assert_not_called()

    # 2. Ambiguous title -> calls LLM fallback
    mock_orchestrator.generate.return_value = MagicMock(success=True, text="Data & AI")
    res2 = await classify_role_family("Quantum Intelligence Strategist", orchestrator=mock_orchestrator)
    assert res2 == "Data & AI"
    mock_orchestrator.generate.assert_called_once()


def test_qualify_job_posting():
    j_valid = RawJobPosting(
        company="TechCorp",
        title="Engineer",
        url="https://example.com/job",
        date=datetime.now(timezone.utc),
        is_remote=True,
    )
    assert qualify_job_posting(j_valid) is True

    j_missing_company = RawJobPosting(
        company="",
        title="Engineer",
        url="https://example.com/job",
        date=datetime.now(timezone.utc),
        is_remote=True,
    )
    assert qualify_job_posting(j_missing_company) is False


def test_job_pydantic_model_validation():
    now = datetime.now(timezone.utc)
    job = Job(
        content={
            "company": "Acme Inc",
            "date": now,
            "is_remote": True,
            "role_family": "Engineering",
        },
        collectedAt=now,
    )
    assert job.recordType == "JOB"
    assert job.content.company == "Acme Inc"

    with pytest.raises(ValidationError):
        Job(
            content={
                "company": "",  # Min length 1 violation
                "date": now,
                "is_remote": True,
            },
            collectedAt=now,
        )


def test_job_repository_save_and_duplicate():
    mock_col = MagicMock()
    mock_col.count_documents.side_effect = [0, 1, 1]  # 1st save check, explicit check, 2nd save check
    mock_col.insert_one = MagicMock()

    mock_db = {"jobs": mock_col}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    repo = JobRepository(client=mock_client)
    repo.setup_indexes()

    now = datetime.now(timezone.utc)
    job = Job(
        content={
            "company": "Acme Corp",
            "date": now,
            "is_remote": True,
            "role_family": "Engineering",
        },
        collectedAt=now,
    )

    url = "https://example.com/jobs/acme-eng"

    # 1. First save -> True
    saved_first = repo.save(job, source_url=url)
    assert saved_first is True

    # 2. Duplicate check -> exists True
    assert repo.exists(url) is True

    # 3. Second save -> False
    saved_second = repo.save(job, source_url=url)
    assert saved_second is False


@pytest.mark.asyncio
async def test_jobs_adapter_discovery():
    import json

    mock_client = AsyncMock()
    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=json.dumps(SAMPLE_JOBS_API_RESPONSE),
    )

    settings = MagicMock()
    settings.jobs_sources = "arbeitnow"

    adapter = JobsAdapter(settings=settings, client=mock_client)
    jobs = await adapter.discover_jobs(limit=10)

    assert len(jobs) == 3
    assert jobs[0].company == "AI Systems Corp"
    await adapter.close()


@pytest.mark.asyncio
async def test_jobs_service_ingest():
    import json

    settings = MagicMock()
    settings.mongodb_uri = "mongodb://localhost:27017"
    settings.mongodb_database = "test_ai_intelligence_pipeline"
    settings.jobs_sources = "arbeitnow"

    mock_client = AsyncMock()
    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=json.dumps(SAMPLE_JOBS_API_RESPONSE),
    )

    mock_mongo_col = MagicMock()
    mock_mongo_col.find.side_effect = [
        [],
        [
            {"content": {"url": "https://www.arbeitnow.com/view/senior-ai-engineer-1"}},
            {"content": {"url": "https://www.arbeitnow.com/view/machine-learning-specialist-2"}},
            {"content": {"url": "https://www.arbeitnow.com/view/devops-lead-3"}},
        ],
    ]
    mock_mongo_col.count_documents.side_effect = [0, 0, 0, 1, 1, 1]
    mock_insert_res = MagicMock()
    mock_insert_res.inserted_ids = ["id1", "id2", "id3"]
    mock_mongo_col.insert_many.return_value = mock_insert_res
    mock_cp_col = MagicMock()
    mock_cp_col.find_one.return_value = None
    mock_mongo_db = {"jobs": mock_mongo_col, "checkpoints": mock_cp_col}
    mock_mongo_client = MagicMock()
    mock_mongo_client.__getitem__.return_value = mock_mongo_db

    with patch("src.crawlers.jobs.adapter.AsyncHttpClient.from_settings", return_value=mock_client), patch("src.storage.repositories.jobs.MongoClient", return_value=mock_mongo_client), patch("src.storage.checkpoints.MongoClient", return_value=mock_mongo_client):
        svc = JobsService(settings=settings)
        res1 = await svc.ingest(limit=3)

        assert res1["status"] == "success"
        assert res1["discovered"] == 3
        assert res1["inserted"] == 3
        assert res1["duplicates"] == 0

        # Second run -> duplicates only
        res2 = await svc.ingest(limit=3, resume=False)
        assert res2["status"] == "success"
        assert res2["inserted"] == 0
        assert res2["duplicates"] == 3

