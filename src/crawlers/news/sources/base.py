"""Base class for News sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.crawlers.client import AsyncHttpClient
from src.crawlers.news.models import RawNewsArticle


class BaseNewsSource(ABC):
    """Abstract base class for modular news sources."""

    source_key: str
    source_name: str
    source_url: str

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

    @abstractmethod
    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawNewsArticle]:
        """Fetch raw news articles up to limit starting from offset."""
        pass
