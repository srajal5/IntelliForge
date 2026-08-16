"""Base class for Job sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.crawlers.client import AsyncHttpClient
from src.crawlers.jobs.models import RawJobPosting


class BaseJobSource(ABC):
    """Abstract base class for modular job sources."""

    source_key: str
    source_name: str
    source_url: str

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

    @abstractmethod
    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawJobPosting]:
        """Fetch raw job postings up to limit starting from offset."""
        pass
