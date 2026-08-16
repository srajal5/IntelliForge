"""Job canonical data model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.models.base import CanonicalBase


class JobContent(CanonicalBase):
    """Content payload for a job record."""

    company: str = Field(..., min_length=1, description="Company name.")
    date: datetime = Field(..., description="Job posting date in ISO-8601.")
    is_remote: bool = Field(..., description="Whether the job is remote.")
    role_family: str | None = Field(
        default=None,
        description="Role family (e.g. 'Engineering', 'Research'). None when unavailable.",
    )


class Job(CanonicalBase):
    """Canonical job record.

    Example::

        job = Job(
            content={
                "company": "Acme AI",
                "date": "2026-08-15T00:00:00Z",
                "is_remote": True,
                "role_family": "Engineering",
            },
            collectedAt="2026-08-15T12:00:00Z",
        )
    """

    schemaVersion: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    recordType: Literal["JOB"] = "JOB"
    content: JobContent
    collectedAt: datetime
