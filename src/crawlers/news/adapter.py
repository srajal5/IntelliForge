"""Adapter for crawling News articles across multiple configured sources."""

from __future__ import annotations

import time
from typing import Any

from src.config.settings import Settings, get_settings
from src.crawlers.client import AsyncHttpClient
from src.crawlers.news.models import RawNewsArticle
from src.crawlers.news.sources import BaseNewsSource, get_news_sources
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NewsAdapter:
    """Discovers and parses news articles across multiple modular news sources."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncHttpClient | None = None,
        sources: list[BaseNewsSource] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or AsyncHttpClient.from_settings(self.settings)

        if sources is not None:
            self.sources = sources
        else:
            self.sources = get_news_sources(self.settings.news_sources, self.client)

        self.source_metrics: dict[str, dict[str, Any]] = {}
        for s in self.sources:
            self.source_metrics[s.source_key] = {
                "source_name": s.source_name,
                "requested": 0,
                "discovered": 0,
                "failed": False,
                "error": None,
                "elapsed": 0.0,
            }

    async def discover_articles(self, limit: int = 10, offset: int = 0) -> list[RawNewsArticle]:
        """Fetch news articles from configured sources up to limit with source failure isolation."""
        logger.info("news_discovery_started", sources=[s.source_key for s in self.sources], limit=limit, offset=offset)
        discovered: list[RawNewsArticle] = []

        per_source_limit = max(5, (limit + len(self.sources) - 1) // max(1, len(self.sources)))
        per_source_offset = offset

        for source in self.sources:
            fetch_count = per_source_limit
            s_key = source.source_key
            self.source_metrics[s_key]["requested"] += fetch_count
            start_t = time.monotonic()

            try:
                articles = await source.discover(limit=fetch_count, offset=per_source_offset)
                elapsed = round(time.monotonic() - start_t, 3)
                self.source_metrics[s_key]["discovered"] += len(articles)
                self.source_metrics[s_key]["elapsed"] += elapsed

                logger.info(
                    "news_source_discovered",
                    source=source.source_name,
                    count=len(articles),
                    elapsed=elapsed,
                )
                discovered.extend(articles)

            except Exception as exc:
                elapsed = round(time.monotonic() - start_t, 3)
                self.source_metrics[s_key]["failed"] = True
                self.source_metrics[s_key]["error"] = str(exc)
                self.source_metrics[s_key]["elapsed"] += elapsed

                logger.warning(
                    "news_source_failed_continuing",
                    source=source.source_name,
                    error=str(exc),
                )
                continue  # Source Failure Isolation

        logger.info("news_discovery_completed", count=len(discovered), total_sources=len(self.sources))
        return discovered[:limit]

    async def close(self) -> None:
        """Close underlying HTTP client session."""
        if self.client:
            await self.client.close()
