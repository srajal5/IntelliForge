"""Tests for the ResearchPaper canonical model."""

import pytest
from pydantic import ValidationError

from src.models.research_paper import ResearchPaper


# ------------------------------------------------------------------
# Valid fixtures
# ------------------------------------------------------------------

def _valid_paper_data() -> dict:
    return {
        "content": {
            "title": "Attention Is All You Need",
            "authors": ["Vaswani, A.", "Shazeer, N."],
            "paper_url": "https://arxiv.org/abs/1706.03762",
            "github_url": "https://github.com/tensorflow/tensor2tensor",
            "github_stars": 15000,
            "published_date": "2017-06-12T00:00:00Z",
        },
        "collectedAt": "2026-08-15T12:00:00Z",
    }


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


def test_valid_research_paper():
    p = ResearchPaper(**_valid_paper_data())
    assert p.recordType == "RESEARCH_PAPER"
    assert p.content.title == "Attention Is All You Need"
    assert len(p.content.authors) == 2
    assert p.content.github_stars == 15000


def test_valid_paper_without_github():
    data = _valid_paper_data()
    data["content"]["github_url"] = None
    data["content"]["github_stars"] = None
    p = ResearchPaper(**data)
    assert p.content.github_url is None
    assert p.content.github_stars is None


def test_valid_paper_empty_authors():
    data = _valid_paper_data()
    data["content"]["authors"] = []
    p = ResearchPaper(**data)
    assert p.content.authors == []


def test_paper_json_serialization():
    p = ResearchPaper(**_valid_paper_data())
    d = p.to_dict()
    assert d["recordType"] == "RESEARCH_PAPER"
    assert isinstance(d["content"]["paper_url"], str)
    assert d["content"]["github_stars"] == 15000

    json_str = p.to_json()
    assert '"RESEARCH_PAPER"' in json_str


# ------------------------------------------------------------------
# Invalid cases
# ------------------------------------------------------------------


def test_missing_title():
    data = _valid_paper_data()
    del data["content"]["title"]
    with pytest.raises(ValidationError, match="title"):
        ResearchPaper(**data)


def test_empty_title():
    data = _valid_paper_data()
    data["content"]["title"] = ""
    with pytest.raises(ValidationError, match="title"):
        ResearchPaper(**data)


def test_invalid_paper_url():
    data = _valid_paper_data()
    data["content"]["paper_url"] = "not-a-url"
    with pytest.raises(ValidationError, match="paper_url"):
        ResearchPaper(**data)


def test_invalid_github_url():
    data = _valid_paper_data()
    data["content"]["github_url"] = "not-a-url"
    with pytest.raises(ValidationError, match="github_url"):
        ResearchPaper(**data)


def test_invalid_github_stars_string():
    data = _valid_paper_data()
    data["content"]["github_stars"] = "abc"
    with pytest.raises(ValidationError, match="github_stars"):
        ResearchPaper(**data)


def test_invalid_github_stars_negative():
    data = _valid_paper_data()
    data["content"]["github_stars"] = -100
    with pytest.raises(ValidationError, match="github_stars"):
        ResearchPaper(**data)


def test_invalid_published_date():
    data = _valid_paper_data()
    data["content"]["published_date"] = "last week"
    with pytest.raises(ValidationError, match="published_date"):
        ResearchPaper(**data)


def test_invalid_record_type():
    data = _valid_paper_data()
    data["recordType"] = "NEWS"
    with pytest.raises(ValidationError, match="recordType"):
        ResearchPaper(**data)
