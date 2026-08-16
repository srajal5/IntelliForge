"""Adapter for crawling Startup records across multiple configured sources."""

from __future__ import annotations

import time
from typing import Any

from src.config.settings import Settings, get_settings
from src.crawlers.client import AsyncHttpClient
from src.crawlers.startups.models import RawStartup
from src.crawlers.startups.sources import BaseStartupSource, get_startup_sources
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StartupAdapter:
    """Discovers and parses startup companies across multiple modular startup sources."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncHttpClient | None = None,
        sources: list[BaseStartupSource] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or AsyncHttpClient.from_settings(self.settings)

        if sources is not None:
            self.sources = sources
        else:
            self.sources = get_startup_sources(self.settings.startup_sources, self.client)

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

    async def discover_startups(self, limit: int = 10, offset: int = 0, page: int | None = None) -> list[RawStartup]:
        """Fetch startup companies from configured sources up to limit with source failure isolation."""
        if page is not None and page > 1 and offset == 0:
            offset = (page - 1) * limit

        logger.info("startup_discovery_started", sources=[s.source_key for s in self.sources], limit=limit, offset=offset)
        discovered: list[RawStartup] = []

        per_source_limit = max(1, limit // max(1, len(self.sources)))
        per_source_offset = offset // max(1, len(self.sources))

        for source in self.sources:
            if len(discovered) >= limit:
                break

            fetch_count = min(per_source_limit, limit - len(discovered))
            s_key = source.source_key
            self.source_metrics[s_key]["requested"] += fetch_count
            start_t = time.monotonic()

            try:
                startups = await source.discover(limit=fetch_count, offset=per_source_offset)
                elapsed = round(time.monotonic() - start_t, 3)
                self.source_metrics[s_key]["discovered"] += len(startups)
                self.source_metrics[s_key]["elapsed"] += elapsed

                logger.info(
                    "startup_source_discovered",
                    source=source.source_name,
                    count=len(startups),
                    elapsed=elapsed,
                )
                discovered.extend(startups)

            except Exception as exc:
                elapsed = round(time.monotonic() - start_t, 3)
                self.source_metrics[s_key]["failed"] = True
                self.source_metrics[s_key]["error"] = str(exc)
                self.source_metrics[s_key]["elapsed"] += elapsed

                logger.warning(
                    "startup_source_failed_continuing",
                    source=source.source_name,
                    error=str(exc),
                )
                continue  # Source Failure Isolation

        logger.info("startup_discovery_completed", count=len(discovered), total_sources=len(self.sources))
        return discovered[:limit]

    async def close(self) -> None:
        """Close underlying HTTP client session."""
        if self.client:
            await self.client.close()
