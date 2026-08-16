"""GitHub Repositories multi-topic query segment source for Products."""

from __future__ import annotations

import json
from src.crawlers.products.models import RawProduct
from src.crawlers.products.parser import ProductParser
from src.crawlers.products.sources.base import BaseProductSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

GITHUB_SEARCH_REPOS_API = "https://api.github.com/search/repositories"

PRODUCT_TOPIC_QUERIES = [
    "topic:ai-tool sort:stars",
    "topic:ai sort:stars",
    "topic:llm sort:stars",
    "topic:machine-learning sort:stars",
    "topic:agents sort:stars",
    "topic:rag sort:stars",
    "topic:developer-tools sort:stars",
    "topic:cli-tool sort:stars",
    "topic:saas sort:stars",
    "topic:deep-learning sort:stars",
    "topic:workflow-automation sort:stars",
    "topic:analytics sort:stars",
    "topic:generative-ai sort:stars",
    "topic:gpt sort:stars",
    "topic:copilot sort:stars",
    "topic:artificial-intelligence sort:stars",
    "topic:nlp sort:stars",
    "topic:computer-vision sort:stars",
    "topic:database sort:stars",
    "topic:web-framework sort:stars",
]


class GitHubReposSource(BaseProductSource):
    """Discovers software and AI products using GitHub Repositories Search with topic rotation."""

    source_key = "github_repos"
    source_name = "GitHub Repositories API"
    source_url = "https://api.github.com/search/repositories"

    async def discover_segment(
        self,
        limit: int = 50,
        segment: int = 0,
        page: int = 1,
        per_page: int = 50,
        max_pages_per_segment: int = 10,
    ) -> tuple[list[RawProduct], int, int, bool]:
        """Discover products starting from (segment, page) with automatic query rotation."""
        discovered: list[RawProduct] = []
        curr_segment = segment
        curr_page = page

        while len(discovered) < limit and curr_segment < len(PRODUCT_TOPIC_QUERIES):
            query = PRODUCT_TOPIC_QUERIES[curr_segment]

            if curr_page > max_pages_per_segment:
                logger.info(
                    "github_repos_segment_page_limit_reached",
                    segment=curr_segment,
                    query=query,
                    max_pages=max_pages_per_segment,
                )
                curr_segment += 1
                curr_page = 1
                continue

            url = f"{GITHUB_SEARCH_REPOS_API}?q={query}&per_page={per_page}&page={curr_page}"
            result = await self.client.fetch(url)

            if not result.success or not result.content:
                logger.warning(
                    "github_repos_fetch_failed_exhausted",
                    status=result.status_code,
                    query=query,
                    segment=curr_segment,
                    page=curr_page,
                )
                curr_segment += 1
                curr_page = 1
                continue

            try:
                data = json.loads(result.content)
                items = data.get("items", [])
                if not items:
                    logger.info(
                        "github_repos_segment_no_items",
                        query=query,
                        segment=curr_segment,
                        page=curr_page,
                    )
                    curr_segment += 1
                    curr_page = 1
                    continue
            except Exception as json_err:
                logger.warning(
                    "github_repos_json_failed", error=str(json_err), query=query
                )
                curr_segment += 1
                curr_page = 1
                continue

            for item in items:
                if len(discovered) >= limit:
                    break
                raw_product = ProductParser.parse_item(item)
                if raw_product:
                    discovered.append(raw_product)

            curr_page += 1
            if curr_page > max_pages_per_segment:
                curr_segment += 1
                curr_page = 1

        exhausted_all = curr_segment >= len(PRODUCT_TOPIC_QUERIES)
        return (discovered, curr_segment, curr_page, exhausted_all)

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawProduct]:
        max_pages_per_segment = 10
        per_page = 50
        segment = (offset // (max_pages_per_segment * per_page)) % len(PRODUCT_TOPIC_QUERIES)
        page = ((offset % (max_pages_per_segment * per_page)) // per_page) + 1
        products, _, _, _ = await self.discover_segment(limit=limit, segment=segment, page=page)
        return products
