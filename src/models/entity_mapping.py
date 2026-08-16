"""Entity mapping canonical data model."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, HttpUrl

from src.models.base import CanonicalBase
from src.models.enums import MatchMethod


class EntityMapping(CanonicalBase):
    """Canonical entity mapping record.

    Maps a raw entity name to its canonical form with confidence scoring.

    Example::

        mapping = EntityMapping(
            raw_name="OpenAi",
            normalized_name="openai",
            canonical_name="OpenAI",
            canonical_id="openai-001",
            match_method="fuzzy",
            confidence=0.92,
            source_url="https://openai.com",
            timestamp="2026-08-15T12:00:00Z",
        )
    """

    raw_name: str = Field(..., min_length=1, description="Original entity name as found in the source.")
    normalized_name: str = Field(..., min_length=1, description="Lowercased/cleaned entity name.")
    canonical_name: str = Field(..., min_length=1, description="Canonical display name.")
    canonical_id: str = Field(..., min_length=1, description="Unique identifier for the canonical entity.")
    match_method: MatchMethod = Field(..., description="Method used for matching.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0.",
    )
    source_url: HttpUrl | None = Field(
        default=None,
        description="Source URL for this entity. None when unavailable.",
    )
    timestamp: datetime = Field(..., description="When this mapping was created (ISO-8601).")
