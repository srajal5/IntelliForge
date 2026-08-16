"""Startup canonical data model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.models.base import CanonicalBase, Source


class StartupData(CanonicalBase):
    """Optional data fields for a startup."""

    employeeCount: int | None = Field(
        default=None,
        description="Number of employees. None when unavailable.",
        ge=0,
    )


class StartupContent(CanonicalBase):
    """Content payload for a startup record."""

    entityName: str = Field(
        ..., min_length=1, description="Name of the startup."
    )
    data: StartupData = Field(default_factory=StartupData)


class Startup(CanonicalBase):
    """Canonical startup record.

    Example::

        startup = Startup(
            source={"name": "Crunchbase", "url": "https://crunchbase.com/org/example"},
            content={"entityName": "Acme AI", "data": {"employeeCount": 50}},
            collectedAt="2026-08-15T12:00:00Z",
        )
    """

    schemaVersion: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    recordType: Literal["STARTUP"] = "STARTUP"
    source: Source
    content: StartupContent
    collectedAt: datetime
