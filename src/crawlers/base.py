"""Abstract base crawler interface.

Defines the contract that all crawler backends (aiohttp, Playwright, …)
must implement.  Source-specific crawlers compose a concrete backend
rather than inheriting from it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.crawlers.models import CrawlPolicy, CrawlResult


class BaseCrawler(ABC):
    """Abstract crawler backend.

    Implementations must support:
    - Single-URL fetch with retry.
    - Batch fetch with bounded concurrency.
    - Graceful session/resource cleanup.
    - Async context-manager protocol.
    """

    @abstractmethod
    async def fetch(self, url: str) -> CrawlResult:
        """Fetch a single URL and return a structured result.

        Retries and backoff are handled internally.
        """
        ...

    @abstractmethod
    async def fetch_many(self, urls: list[str]) -> list[CrawlResult]:
        """Fetch multiple URLs concurrently with bounded parallelism.

        Individual failures must not crash the batch.
        The returned list preserves URL-to-result order.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release all resources (sessions, connectors, …)."""
        ...

    # -- context manager helpers ------------------------------------------

    async def __aenter__(self) -> BaseCrawler:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
