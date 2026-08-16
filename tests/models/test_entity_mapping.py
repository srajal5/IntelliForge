"""Tests for the EntityMapping canonical model."""

import pytest
from pydantic import ValidationError

from src.models.entity_mapping import EntityMapping


# ------------------------------------------------------------------
# Valid fixtures
# ------------------------------------------------------------------

def _valid_mapping_data() -> dict:
    return {
        "raw_name": "OpenAi",
        "normalized_name": "openai",
        "canonical_name": "OpenAI",
        "canonical_id": "openai-001",
        "match_method": "fuzzy",
        "confidence": 0.92,
        "source_url": "https://openai.com",
        "timestamp": "2026-08-15T12:00:00Z",
    }


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


def test_valid_mapping():
    m = EntityMapping(**_valid_mapping_data())
    assert m.raw_name == "OpenAi"
    assert m.canonical_name == "OpenAI"
    assert m.match_method.value == "fuzzy"
    assert m.confidence == 0.92


def test_valid_mapping_all_match_methods():
    for method in ("exact", "normalized", "alias", "fuzzy", "llm", "unresolved"):
        data = _valid_mapping_data()
        data["match_method"] = method
        m = EntityMapping(**data)
        assert m.match_method.value == method


def test_valid_mapping_no_source_url():
    data = _valid_mapping_data()
    data["source_url"] = None
    m = EntityMapping(**data)
    assert m.source_url is None


def test_valid_confidence_boundaries():
    for conf in (0.0, 0.5, 1.0):
        data = _valid_mapping_data()
        data["confidence"] = conf
        m = EntityMapping(**data)
        assert m.confidence == conf


def test_mapping_json_serialization():
    m = EntityMapping(**_valid_mapping_data())
    d = m.to_dict()
    assert d["match_method"] == "fuzzy"
    assert d["confidence"] == 0.92
    assert isinstance(d["source_url"], str)

    json_str = m.to_json()
    assert '"fuzzy"' in json_str
    assert '"openai-001"' in json_str


# ------------------------------------------------------------------
# Invalid cases
# ------------------------------------------------------------------


def test_invalid_confidence_too_high():
    data = _valid_mapping_data()
    data["confidence"] = 1.5
    with pytest.raises(ValidationError, match="confidence"):
        EntityMapping(**data)


def test_invalid_confidence_negative():
    data = _valid_mapping_data()
    data["confidence"] = -0.1
    with pytest.raises(ValidationError, match="confidence"):
        EntityMapping(**data)


def test_invalid_confidence_string():
    data = _valid_mapping_data()
    data["confidence"] = "high"
    with pytest.raises(ValidationError, match="confidence"):
        EntityMapping(**data)


def test_invalid_source_url():
    data = _valid_mapping_data()
    data["source_url"] = "not-a-url"
    with pytest.raises(ValidationError, match="source_url"):
        EntityMapping(**data)


def test_invalid_timestamp():
    data = _valid_mapping_data()
    data["timestamp"] = "not-a-date"
    with pytest.raises(ValidationError, match="timestamp"):
        EntityMapping(**data)


def test_invalid_match_method():
    data = _valid_mapping_data()
    data["match_method"] = "magic"
    with pytest.raises(ValidationError, match="match_method"):
        EntityMapping(**data)


def test_missing_raw_name():
    data = _valid_mapping_data()
    del data["raw_name"]
    with pytest.raises(ValidationError, match="raw_name"):
        EntityMapping(**data)


def test_missing_canonical_id():
    data = _valid_mapping_data()
    del data["canonical_id"]
    with pytest.raises(ValidationError, match="canonical_id"):
        EntityMapping(**data)
