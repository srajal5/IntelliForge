"""Crawl-test service — lightweight demo of the async crawler engine."""

from __future__ import annotations

from src.crawlers.client import AsyncHttpClient
from src.crawlers.models import CrawlResult
from src.utils.logging import get_logger

logger = get_logger("services.crawl_test")


class CrawlTestService:
    """Run a quick fetch against a safe endpoint to verify the crawler."""

    def __init__(self, settings) -> None:
        self._settings = settings

    async def run(
        self, url: str = "https://example.com", concurrency: int | None = None
    ) -> CrawlResult:
        """Fetch a single URL and return the CrawlResult."""
        client = AsyncHttpClient.from_settings(self._settings)
        if concurrency is not None:
            client._concurrency = concurrency
            client._semaphore = __import__("asyncio").Semaphore(concurrency)

        logger.info("crawl_test_started", url=url)
        try:
            result = await client.fetch(url)
            logger.info(
                "crawl_test_complete",
                url=result.url,
                status=result.status_code,
                success=result.success,
                response_time=result.response_time,
                content_length=result.content_length,
                attempts=result.attempts,
            )
            return result
        finally:
            await client.close()

    async def run_batch(
        self,
        urls: list[str],
        concurrency: int | None = None,
    ) -> list[CrawlResult]:
        """Fetch multiple URLs concurrently and return results."""
        client = AsyncHttpClient.from_settings(self._settings)
        if concurrency is not None:
            client._concurrency = concurrency
            client._semaphore = __import__("asyncio").Semaphore(concurrency)

        logger.info("crawl_batch_started", url_count=len(urls))
        try:
            results = await client.fetch_many(urls)
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            logger.info(
                "crawl_batch_complete",
                total=len(results),
                successful=successful,
                failed=failed,
            )
            return results
        finally:
            await client.close()
