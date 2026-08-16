"""Research paper adapter for arXiv ingestion using AsyncHttpClient."""

from __future__ import annotations

import urllib.parse
from typing import Sequence

from src.config.settings import Settings, get_settings
from src.crawlers.base import BaseCrawler
from src.crawlers.client import AsyncHttpClient
from src.crawlers.models import CrawlResult
from src.crawlers.research.github import GitHubDiscoverer, GitHubMetadataFetcher
from src.crawlers.research.models import RawPaper
from src.crawlers.research.parser import ArxivParser
from src.utils.logging import get_logger

logger = get_logger(__name__)

ARXIV_API_BASE = "http://export.arxiv.org/api/query"
DEFAULT_CATEGORY_QUERY = "cat:cs.AI OR cat:cs.CL OR cat:cs.CV OR cat:cs.LG"


class ResearchAdapter(BaseCrawler):
    """Adapter for discovering and fetching research papers from arXiv."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncHttpClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or AsyncHttpClient.from_settings(self.settings)
        self.github_fetcher = GitHubMetadataFetcher(
            client=self.client, token=self.settings.github_token
        )

    async def fetch(self, url: str) -> CrawlResult:
        """Fetch a single URL via the underlying HTTP client."""
        return await self.client.fetch(url)

    async def fetch_many(self, urls: Sequence[str]) -> list[CrawlResult]:
        """Fetch multiple URLs concurrently."""
        return await self.client.fetch_many(urls)

    async def close(self) -> None:
        """Close HTTP client session resources."""
        await self.client.close()

    # ------------------------------------------------------------------
    # Discovery & Ingestion
    # ------------------------------------------------------------------

    async def discover_papers(
        self,
        limit: int = 10,
        query: str = DEFAULT_CATEGORY_QUERY,
        enrich_github: bool = True,
        start: int = 0,
    ) -> list[RawPaper]:
        """Discover research papers from arXiv up to `limit`.

        Handles pagination and optional GitHub URL discovery / star retrieval.
        """
        papers: list[RawPaper] = []
        page_size = min(limit, 50)

        logger.info("arxiv_discovery_started", limit=limit, query=query)

        while len(papers) < limit:
            fetch_count = min(page_size, limit - len(papers))
            url = self._build_query_url(query=query, start=start, max_results=fetch_count)

            result = await self.fetch(url)
            if not result.success or not result.content:
                logger.error(
                    "arxiv_fetch_failed",
                    url=url,
                    status=result.status_code,
                    error=result.error,
                )
                break

            parsed_page = ArxivParser.parse_feed(result.content)
            if not parsed_page:
                logger.info("arxiv_no_more_results", start=start)
                break

            for paper in parsed_page:
                if len(papers) >= limit:
                    break

                # GitHub discovery from abstract text
                gh_url = GitHubDiscoverer.discover_github_url(paper.summary)
                if gh_url:
                    paper.github_url = gh_url
                    if enrich_github:
                        val_url, stars = await self.github_fetcher.fetch_stars(gh_url)
                        paper.github_url = val_url
                        paper.github_stars = stars

                papers.append(paper)

            start += len(parsed_page)

        logger.info("arxiv_discovery_completed", discovered=len(papers))
        return papers

    @staticmethod
    def _build_query_url(query: str, start: int, max_results: int) -> str:
        """Construct arXiv API search query URL."""
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        encoded = urllib.parse.urlencode(params)
        return f"{ARXIV_API_BASE}?{encoded}"
