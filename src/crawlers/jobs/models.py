"""Data models for Job postings crawling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawJobPosting:
    """Raw job posting data extracted from job feed or API."""

    company: str
    title: str
    url: str
    date: datetime
    is_remote: bool
    description: str | None = None
    role_family: str | None = None
    source_name: str = "Arbeitnow Tech Jobs"
    source_url: str = "https://www.arbeitnow.com/api/job-board-api"
    is_qualified: bool = True
