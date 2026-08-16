"""News canonical data model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl

from src.models.base import CanonicalBase, Source


class NewsContent(CanonicalBase):
    """Content payload for a news record."""

    title: str = Field(..., min_length=1, description="Article title.")
    url: HttpUrl = Field(..., description="Article URL.")
    published_date: datetime = Field(
        ..., description="Publication date in ISO-8601."
    )
    full_text: str | None = Field(
        default=None,
        description="Extracted article content. None when unavailable.",
    )


class News(CanonicalBase):
    """Canonical news record.

    Example::

        news = News(
            source={"name": "TechCrunch", "url": "https://techcrunch.com"},
            content={
                "title": "New AI Startup Raises $10M",
                "url": "https://techcrunch.com/2026/08/15/example",
                "published_date": "2026-08-15T09:00:00Z",
                "full_text": "Full article text here...",
            },
            collectedAt="2026-08-15T12:00:00Z",
        )
    """

    schemaVersion: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    recordType: Literal["NEWS"] = "NEWS"
    source: Source
    content: NewsContent
    collectedAt: datetime
