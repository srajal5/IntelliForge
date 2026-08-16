"""Raw research paper data models before canonical validation."""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class RawPaper:
    """Raw metadata extracted from a research paper source feed."""

    title: str
    authors: list[str] = field(default_factory=list)
    paper_url: str = ""
    summary: str = ""
    published_date: datetime | None = None
    source_name: str = "arXiv"
    source_url: str = "http://export.arxiv.org/api/query"
    github_url: str | None = None
    github_stars: int | None = None
