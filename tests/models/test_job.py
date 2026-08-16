"""Tests for the Job canonical model."""

import pytest
from pydantic import ValidationError

from src.models.job import Job


# ------------------------------------------------------------------
# Valid fixtures
# ------------------------------------------------------------------

def _valid_job_data() -> dict:
    return {
        "content": {
            "company": "Acme AI",
            "date": "2026-08-15T00:00:00Z",
            "is_remote": True,
            "role_family": "Engineering",
        },
        "collectedAt": "2026-08-15T12:00:00Z",
    }


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


def test_valid_job():
    j = Job(**_valid_job_data())
    assert j.recordType == "JOB"
    assert j.content.company == "Acme AI"
    assert j.content.is_remote is True
    assert j.content.role_family == "Engineering"


def test_valid_job_no_role_family():
    data = _valid_job_data()
    data["content"]["role_family"] = None
    j = Job(**data)
    assert j.content.role_family is None


def test_valid_job_not_remote():
    data = _valid_job_data()
    data["content"]["is_remote"] = False
    j = Job(**data)
    assert j.content.is_remote is False


def test_job_json_serialization():
    j = Job(**_valid_job_data())
    d = j.to_dict()
    assert d["recordType"] == "JOB"
    assert d["content"]["is_remote"] is True

    json_str = j.to_json()
    assert '"JOB"' in json_str


# ------------------------------------------------------------------
# Invalid cases
# ------------------------------------------------------------------


def test_invalid_date():
    data = _valid_job_data()
    data["content"]["date"] = "not-a-date"
    with pytest.raises(ValidationError, match="date"):
        Job(**data)


def test_invalid_is_remote_string():
    data = _valid_job_data()
    data["content"]["is_remote"] = "maybe"
    with pytest.raises(ValidationError, match="is_remote"):
        Job(**data)


def test_invalid_record_type():
    data = _valid_job_data()
    data["recordType"] = "STARTUP"
    with pytest.raises(ValidationError, match="recordType"):
        Job(**data)


def test_missing_company():
    data = _valid_job_data()
    del data["content"]["company"]
    with pytest.raises(ValidationError, match="company"):
        Job(**data)


def test_missing_is_remote():
    data = _valid_job_data()
    del data["content"]["is_remote"]
    with pytest.raises(ValidationError, match="is_remote"):
        Job(**data)


def test_invalid_collected_at():
    data = _valid_job_data()
    data["collectedAt"] = "tomorrow"
    with pytest.raises(ValidationError, match="collectedAt"):
        Job(**data)
