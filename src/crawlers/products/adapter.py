"""Adapter for crawling Product records across multiple configured sources."""

from __future__ import annotations

import time
from typing import Any

from src.config.settings import Settings, get_settings
from src.crawlers.client import AsyncHttpClient
from src.crawlers.products.models import RawProduct
from src.crawlers.products.sources import BaseProductSource, get_product_sources
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProductAdapter:
    """Discovers and parses product items across multiple modular product sources."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncHttpClient | None = None,
        sources: list[BaseProductSource] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or AsyncHttpClient.from_settings(self.settings)

        if sources is not None:
            self.sources = sources
        else:
            self.sources = get_product_sources(self.settings.product_sources, self.client)

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

    async def discover_products(
        self,
        limit: int = 10,
        query: str = "topic:ai",
        offset: int = 0,
        page: int | None = None,
        segment: int = 0,
        return_tuple: bool = False,
    ) -> tuple[list[RawProduct], int, int, bool] | list[RawProduct]:
        """Fetch products from configured sources with topic rotation and failure isolation."""
        curr_page = page if page is not None else 1
        if page is not None and page > 1 and offset == 0:
            offset = (page - 1) * limit

        logger.info(
            "product_discovery_started",
            sources=[s.source_key for s in self.sources],
            limit=limit,
            segment=segment,
            page=curr_page,
        )
        discovered: list[RawProduct] = []
        next_segment = segment
        next_page = curr_page
        exhausted_all = False

        for source in self.sources:
            if len(discovered) >= limit:
                break

            fetch_count = limit - len(discovered)
            s_key = source.source_key
            self.source_metrics[s_key]["requested"] += fetch_count
            start_t = time.monotonic()

            try:
                if hasattr(source, "discover_segment"):
                    products, next_segment, next_page, exhausted_all = await source.discover_segment(
                        limit=fetch_count, segment=segment, page=curr_page
                    )
                else:
                    products = await source.discover(limit=fetch_count, offset=offset)

                elapsed = round(time.monotonic() - start_t, 3)
                self.source_metrics[s_key]["discovered"] += len(products)
                self.source_metrics[s_key]["elapsed"] += elapsed

                logger.info(
                    "product_source_discovered",
                    source=source.source_name,
                    count=len(products),
                    elapsed=elapsed,
                )
                discovered.extend(products)

            except Exception as exc:
                elapsed = round(time.monotonic() - start_t, 3)
                self.source_metrics[s_key]["failed"] = True
                self.source_metrics[s_key]["error"] = str(exc)
                self.source_metrics[s_key]["elapsed"] += elapsed

                logger.warning(
                    "product_source_failed_continuing",
                    source=source.source_name,
                    error=str(exc),
                )
                continue  # Source Failure Isolation

        logger.info(
            "product_discovery_completed",
            count=len(discovered),
            total_sources=len(self.sources),
            next_segment=next_segment,
            next_page=next_page,
        )

        res_items = discovered[:limit]
        if return_tuple:
            return (res_items, next_segment, next_page, exhausted_all)
        return res_items

    async def close(self) -> None:
        """Close underlying HTTP client session."""
        if self.client:
            await self.client.close()
