"""Crawl cache interface.

Defines the abstract cache contract and provides a NullCache
(no-op) implementation.  A Redis-backed implementation will be
added in a later scaling phase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.crawlers.models import CrawlResult


class CrawlCache(ABC):
    """Abstract interface for caching CrawlResults."""

    @abstractmethod
    async def get(self, fingerprint: str) -> CrawlResult | None:
        """Return a cached result or None."""
        ...

    @abstractmethod
    async def set(
        self, fingerprint: str, result: CrawlResult, ttl: int | None = None
    ) -> None:
        """Store a result, optionally with a TTL in seconds."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Flush the entire cache."""
        ...


class NullCache(CrawlCache):
    """No-op cache — every lookup misses, nothing is stored."""

    async def get(self, fingerprint: str) -> CrawlResult | None:
        return None

    async def set(
        self, fingerprint: str, result: CrawlResult, ttl: int | None = None
    ) -> None:
        pass

    async def clear(self) -> None:
        pass
