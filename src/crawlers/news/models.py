"""Data models for News crawling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawNewsArticle:
    """Raw news article data extracted from feed or web page."""

    title: str
    url: str
    published_date: datetime
    full_text: str | None = None
    source_name: str = "TechCrunch AI Feed"
    source_url: str = "https://techcrunch.com/category/artificial-intelligence/"
    is_qualified: bool = True
