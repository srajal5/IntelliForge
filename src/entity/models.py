"""Canonical entity model for Entity Resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class CanonicalEntity(BaseModel):
    """Canonical representation of an organization or company entity.

    Example::

        entity = CanonicalEntity(
            canonical_id="ent_openai_001",
            canonical_name="OpenAI",
            entity_type="STARTUP",
            aliases=["Open AI", "OpenAI Inc.", "OpenAI, Inc."],
            source_urls=["https://openai.com"],
        )
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        extra="forbid",
        populate_by_name=True,
    )

    canonical_id: str = Field(..., min_length=1, description="Unique canonical entity ID.")
    canonical_name: str = Field(..., min_length=1, description="Canonical display name.")
    entity_type: str = Field(
        default="STARTUP",
        description="Entity type classification (e.g. STARTUP, COMPANY, ORGANIZATION).",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="List of known alias strings for this canonical entity.",
    )
    source_urls: list[str] = Field(
        default_factory=list,
        description="Source URLs associated with this canonical entity.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp (ISO-8601).",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last updated timestamp (ISO-8601).",
    )

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dictionary."""
        return self.model_dump(mode="json")
