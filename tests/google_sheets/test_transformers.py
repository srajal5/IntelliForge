"""Test record-to-sheet row transformations across all 5 verticals."""

from src.integrations.google_sheets.transformers import (
    JOBS_HEADERS,
    NEWS_HEADERS,
    PRODUCTS_HEADERS,
    RESEARCH_PAPERS_HEADERS,
    STARTUPS_HEADERS,
    transform_job,
    transform_news,
    transform_product,
    transform_research_paper,
    transform_startup,
)


def test_transform_research_paper_valid():
    doc = {
        "content": {
            "title": "Attention Is All You Need",
            "paper_url": "https://arxiv.org/abs/1706.03762",
            "authors": ["Vaswani, A.", "Shazeer, N."],
            "published_date": "2017-06-12T00:00:00Z",
            "github_url": "https://github.com/tensorflow/tensor2tensor",
            "github_stars": 15000,
            "abstract": "We propose the Transformer architecture...",
        },
        "source": {"name": "arXiv", "url": "https://arxiv.org"},
        "collectedAt": "2026-08-16T10:00:00Z",
        "canonical_entity_id": "ent_vaswani_1706",
    }
    row = transform_research_paper(doc)
    assert row is not None
    assert len(row) == len(RESEARCH_PAPERS_HEADERS)
    assert row[0] == "https://arxiv.org/abs/1706.03762"
    assert row[1] == "Attention Is All You Need"
    assert row[2] == "Vaswani, A., Shazeer, N."
    assert row[4] == "https://github.com/tensorflow/tensor2tensor"
    assert row[5] == 15000
    assert row[10] == "ent_vaswani_1706"


def test_transform_research_paper_invalid():
    assert transform_research_paper({"content": {}}) is None
    assert transform_research_paper({"content": {"title": "Paper Without URL"}}) is None


def test_transform_startup_valid_and_non_inference():
    doc = {
        "content": {
            "entityName": "OpenAI",
            "data": {
                "employeeCount": None,  # Must NOT infer
            },
        },
        "source": {"name": "GitHub Organizations", "url": "https://github.com/openai"},
        "provenance": {
            "category": "AI_RESEARCH_LAB",
            "is_qualified": True,
        },
        "canonical_entity_id": "ent_openai_001",
        "collectedAt": "2026-08-16T10:00:00Z",
    }
    row = transform_startup(doc)
    assert row is not None
    assert len(row) == len(STARTUPS_HEADERS)
    assert row[0] == "OpenAI"
    assert row[1] == "https://github.com/openai"
    assert row[3] == ""  # employee count is None, NOT inferred
    assert row[4] == ""  # founded date is missing, NOT inferred
    assert row[5] == ""  # location is missing, NOT inferred
    assert row[6] == ""  # funding is missing, NOT inferred
    assert row[8] == "AI_RESEARCH_LAB"
    assert row[9] == "QUALIFIED"


def test_transform_startup_invalid():
    assert transform_startup({"content": {}}) is None


def test_transform_product_valid_and_license_separation():
    doc = {
        "content": {
            "startupName": "openclaw",
            "pricingModel": None,  # Must NOT infer from MIT license!
        },
        "source": {"name": "GitHub Products", "url": "https://github.com/openclaw/openclaw"},
        "provenance": {
            "product_name": "openclaw",
            "description": "An open source agentic crawler",
            "license": "MIT",
            "category": "APPLICATION_TOOL",
        },
        "canonical_startup_id": "unresolved_openclaw",
        "collectedAt": "2026-08-16T10:00:00Z",
    }
    row = transform_product(doc)
    assert row is not None
    assert len(row) == len(PRODUCTS_HEADERS)
    assert row[0] == "openclaw"
    assert row[1] == "openclaw"
    assert row[4] == ""  # Pricing model must NOT be inferred from license "MIT"
    assert row[6] == "MIT"  # License preserved separately
    assert row[7] == "APPLICATION_TOOL"


def test_transform_product_invalid():
    assert transform_product({"content": {}}) is None


def test_transform_news_valid_and_unmodified_text():
    doc = {
        "content": {
            "title": "AI Breakthough Announced",
            "url": "https://techcrunch.com/2026/08/15/ai-breakthrough",
            "published_date": "2026-08-15T20:00:00Z",
            "full_text": "Exact article text with original characters: \nSpecial format.",
        },
        "source": {"name": "TechCrunch", "url": "https://techcrunch.com"},
        "collectedAt": "2026-08-16T10:00:00Z",
    }
    row = transform_news(doc)
    assert row is not None
    assert len(row) == len(NEWS_HEADERS)
    assert row[0] == "AI Breakthough Announced"
    assert row[1] == "https://techcrunch.com/2026/08/15/ai-breakthrough"
    assert row[3] == "Exact article text with original characters: \nSpecial format."  # Unmodified text


def test_transform_news_invalid():
    assert transform_news({"content": {"title": "Missing URL"}}) is None


def test_transform_job_valid_and_no_fabrication():
    doc = {
        "content": {
            "company": "Anthropic",
            "date": "2026-08-16T08:00:00Z",
            "is_remote": True,
            "role_family": "Research",
        },
        "source_url": "https://remoteok.com/jobs/123",
        "collectedAt": "2026-08-16T10:00:00Z",
    }
    row = transform_job(doc)
    assert row is not None
    assert len(row) == len(JOBS_HEADERS)
    assert row[0] == "Anthropic"
    assert row[1] == "2026-08-16T08:00:00Z"
    assert row[2] == "True"
    assert row[3] == "Research"
    assert row[4] == "https://remoteok.com/jobs/123"


def test_transform_job_invalid():
    assert transform_job({"content": {}}) is None
