"""Research paper canonical data model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl

from src.models.base import CanonicalBase


class ResearchPaperContent(CanonicalBase):
    """Content payload for a research paper record."""

    title: str = Field(..., min_length=1, description="Paper title.")
    authors: list[str] = Field(
        default_factory=list, description="List of author names."
    )
    paper_url: HttpUrl = Field(..., description="URL to the paper.")
    github_url: HttpUrl | None = Field(
        default=None,
        description="URL to the associated GitHub repository. None when unavailable.",
    )
    github_stars: int | None = Field(
        default=None,
        description="GitHub star count. None when unavailable.",
        ge=0,
    )
    published_date: datetime = Field(
        ..., description="Publication date in ISO-8601."
    )


class ResearchPaper(CanonicalBase):
    """Canonical research paper record.

    Example::

        paper = ResearchPaper(
            content={
                "title": "Attention Is All You Need",
                "authors": ["Vaswani, A.", "Shazeer, N."],
                "paper_url": "https://arxiv.org/abs/1706.03762",
                "github_url": "https://github.com/tensorflow/tensor2tensor",
                "github_stars": 15000,
                "published_date": "2017-06-12T00:00:00Z",
            },
            collectedAt="2026-08-15T12:00:00Z",
        )
    """

    schemaVersion: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    recordType: Literal["RESEARCH_PAPER"] = "RESEARCH_PAPER"
    content: ResearchPaperContent
    collectedAt: datetime
