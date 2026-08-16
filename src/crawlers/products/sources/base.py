"""Base class for Product sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.crawlers.client import AsyncHttpClient
from src.crawlers.products.models import RawProduct


class BaseProductSource(ABC):
    """Abstract base class for modular product sources."""

    source_key: str
    source_name: str
    source_url: str

    def __init__(self, client: AsyncHttpClient) -> None:
        self.client = client

    @abstractmethod
    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawProduct]:
        """Fetch raw product items up to limit starting from offset."""
        pass
