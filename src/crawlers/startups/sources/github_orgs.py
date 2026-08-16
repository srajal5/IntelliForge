"""GitHub Organizations multi-query segment source for Startups."""

import json
from src.crawlers.startups.models import RawStartup
from src.crawlers.startups.parser import StartupParser
from src.crawlers.startups.sources.base import BaseStartupSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

GITHUB_SEARCH_ORGS_API = "https://api.github.com/search/users"

STARTUP_SEARCH_QUERIES = [
    "type:org created:>2024-01-01",
    "type:org created:2023-01-01..2023-12-31",
    "type:org created:2022-01-01..2022-12-31",
    "type:org created:2020-01-01..2021-12-31",
    "type:org created:2018-01-01..2019-12-31",
    "type:org created:2015-01-01..2017-12-31",
    "type:org location:california",
    "type:org location:london",
    "type:org location:berlin",
    "type:org location:sanfrancisco",
]


class GitHubOrgsSource(BaseStartupSource):
    """Discovers startup companies using GitHub Organizations Search with segment query rotation."""

    source_key = "github_orgs"
    source_name = "GitHub Organizations API"
    source_url = "https://api.github.com/search/users"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawStartup]:
        discovered: list[RawStartup] = []
        per_page = 50

        total_pages_per_query = 10
        query_index = (offset // (total_pages_per_query * per_page)) % len(STARTUP_SEARCH_QUERIES)
        offset_within_query = offset % (total_pages_per_query * per_page)
        page = (offset_within_query // per_page) + 1

        query = STARTUP_SEARCH_QUERIES[query_index]

        while len(discovered) < limit and page <= total_pages_per_query:
            url = f"{GITHUB_SEARCH_ORGS_API}?q={query}&per_page={per_page}&page={page}"

            result = await self.client.fetch(url)
            if not result.success or not result.content:
                logger.warning("github_orgs_fetch_failed", status=result.status_code, query=query, page=page)
                break

            try:
                data = json.loads(result.content)
                items = data.get("items", [])
                if not items:
                    break
            except Exception as json_err:
                logger.warning("github_orgs_json_failed", error=str(json_err))
                break

            item_offset = (offset_within_query % per_page) if page == (offset_within_query // per_page) + 1 else 0
            selected_items = items[item_offset:] if item_offset < len(items) else items

            for item in selected_items:
                if len(discovered) >= limit:
                    break

                raw_startup = StartupParser.parse_item(item)
                if raw_startup:
                    discovered.append(raw_startup)

            page += 1

        return discovered
