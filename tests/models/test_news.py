"""Tests for the News canonical model."""

import pytest
from pydantic import ValidationError

from src.models.news import News


# ------------------------------------------------------------------
# Valid fixtures
# ------------------------------------------------------------------

def _valid_news_data() -> dict:
    return {
        "source": {"name": "TechCrunch", "url": "https://techcrunch.com"},
        "content": {
            "title": "New AI Startup Raises $10M",
            "url": "https://techcrunch.com/2026/08/15/new-ai-startup",
            "published_date": "2026-08-15T09:00:00Z",
            "full_text": "Full article text here...",
        },
        "collectedAt": "2026-08-15T12:00:00Z",
    }


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


def test_valid_news():
    n = News(**_valid_news_data())
    assert n.recordType == "NEWS"
    assert n.content.title == "New AI Startup Raises $10M"
    assert n.content.full_text == "Full article text here..."


def test_valid_news_no_full_text():
    data = _valid_news_data()
    data["content"]["full_text"] = None
    n = News(**data)
    assert n.content.full_text is None


def test_news_json_serialization():
    n = News(**_valid_news_data())
    d = n.to_dict()
    assert d["recordType"] == "NEWS"
    assert isinstance(d["source"]["url"], str)
    assert isinstance(d["content"]["url"], str)

    json_str = n.to_json()
    assert '"NEWS"' in json_str


# ------------------------------------------------------------------
# Invalid cases
# ------------------------------------------------------------------


def test_invalid_source_url():
    data = _valid_news_data()
    data["source"]["url"] = "not-a-url"
    with pytest.raises(ValidationError, match="url"):
        News(**data)


def test_invalid_article_url():
    data = _valid_news_data()
    data["content"]["url"] = "not-a-url"
    with pytest.raises(ValidationError, match="url"):
        News(**data)


def test_invalid_published_date():
    data = _valid_news_data()
    data["content"]["published_date"] = "last tuesday"
    with pytest.raises(ValidationError, match="published_date"):
        News(**data)


def test_missing_title():
    data = _valid_news_data()
    del data["content"]["title"]
    with pytest.raises(ValidationError, match="title"):
        News(**data)


def test_empty_title():
    data = _valid_news_data()
    data["content"]["title"] = ""
    with pytest.raises(ValidationError, match="title"):
        News(**data)


def test_invalid_collected_at():
    data = _valid_news_data()
    data["collectedAt"] = "invalid"
    with pytest.raises(ValidationError, match="collectedAt"):
        News(**data)


def test_missing_source():
    data = _valid_news_data()
    del data["source"]
    with pytest.raises(ValidationError, match="source"):
        News(**data)
