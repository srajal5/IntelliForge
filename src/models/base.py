"""Shared base components for canonical data models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class CanonicalBase(BaseModel):
    """Base configuration shared by all canonical models.

    - Strips whitespace from strings.
    - Validates default values.
    - Forbids extra fields to enforce strict schemas.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        extra="forbid",
        populate_by_name=True,
    )

    def to_dict(self) -> dict:
        """Serialize to a dict with JSON-compatible types (URLs as strings, etc.)."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Serialize to a canonical JSON string."""
        return self.model_dump_json(indent=2)


class Source(CanonicalBase):
    """Data source metadata — shared by Startup, Product, and News."""

    name: str
    url: HttpUrl
