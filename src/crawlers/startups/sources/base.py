"""Base class for Startup sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.crawlers.client import AsyncHttpClient
from src.crawlers.startups.models import RawStartup


class BaseStartupSource(ABC):
    """Abstract base class for modular startup sources."""

    source_key: str
    source_name: str
    source_url: str

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

    @abstractmethod
    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawStartup]:
        """Fetch raw startup companies up to limit starting from offset."""
        pass
