"""Tests for the Startup canonical model."""

import pytest
from pydantic import ValidationError

from src.models.startup import Startup


# ------------------------------------------------------------------
# Valid fixtures
# ------------------------------------------------------------------

def _valid_startup_data() -> dict:
    return {
        "source": {"name": "Crunchbase", "url": "https://crunchbase.com/org/acme"},
        "content": {"entityName": "Acme AI", "data": {"employeeCount": 50}},
        "collectedAt": "2026-08-15T12:00:00Z",
    }


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


def test_valid_startup():
    s = Startup(**_valid_startup_data())
    assert s.recordType == "STARTUP"
    assert s.schemaVersion == "1.0"
    assert s.content.entityName == "Acme AI"
    assert s.content.data.employeeCount == 50


def test_valid_startup_without_employee_count():
    data = _valid_startup_data()
    data["content"]["data"] = {}
    s = Startup(**data)
    assert s.content.data.employeeCount is None


def test_valid_startup_no_data_block():
    data = _valid_startup_data()
    del data["content"]["data"]
    s = Startup(**data)
    assert s.content.data.employeeCount is None


def test_startup_json_serialization():
    s = Startup(**_valid_startup_data())
    d = s.to_dict()
    assert d["recordType"] == "STARTUP"
    assert isinstance(d["source"]["url"], str)
    assert d["content"]["data"]["employeeCount"] == 50

    json_str = s.to_json()
    assert '"STARTUP"' in json_str


# ------------------------------------------------------------------
# Invalid cases
# ------------------------------------------------------------------


def test_invalid_record_type():
    data = _valid_startup_data()
    data["recordType"] = "PRODUCT"
    with pytest.raises(ValidationError, match="recordType"):
        Startup(**data)


def test_invalid_source_url():
    data = _valid_startup_data()
    data["source"]["url"] = "not-a-url"
    with pytest.raises(ValidationError, match="url"):
        Startup(**data)


def test_invalid_employee_count_string():
    data = _valid_startup_data()
    data["content"]["data"]["employeeCount"] = "abc"
    with pytest.raises(ValidationError, match="employeeCount"):
        Startup(**data)


def test_invalid_employee_count_negative():
    data = _valid_startup_data()
    data["content"]["data"]["employeeCount"] = -5
    with pytest.raises(ValidationError, match="employeeCount"):
        Startup(**data)


def test_invalid_timestamp():
    data = _valid_startup_data()
    data["collectedAt"] = "not-a-date"
    with pytest.raises(ValidationError, match="collectedAt"):
        Startup(**data)


def test_missing_entity_name():
    data = _valid_startup_data()
    del data["content"]["entityName"]
    with pytest.raises(ValidationError, match="entityName"):
        Startup(**data)


def test_empty_entity_name():
    data = _valid_startup_data()
    data["content"]["entityName"] = ""
    with pytest.raises(ValidationError, match="entityName"):
        Startup(**data)


def test_extra_field_rejected():
    data = _valid_startup_data()
    data["unknownField"] = "should fail"
    with pytest.raises(ValidationError, match="unknownField"):
        Startup(**data)
