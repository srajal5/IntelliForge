"""Hacker News Algolia API news source."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.crawlers.news.models import RawNewsArticle
from src.crawlers.news.parser import extract_clean_text
from src.crawlers.news.qualifier import qualify_news_article
from src.crawlers.news.sources.base import BaseNewsSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

HN_ALGOLIA_API = "https://hn.algolia.com/api/v1/search"


class HackerNewsSource(BaseNewsSource):
    """Discovers AI news stories from Hacker News via the public Algolia API."""

    source_key = "hackernews"
    source_name = "Hacker News AI"
    source_url = "https://news.ycombinator.com"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawNewsArticle]:
        discovered: list[RawNewsArticle] = []
        per_page = 50
        page = offset // per_page
        item_offset = offset % per_page

        url = f"{HN_ALGOLIA_API}?query=AI&tags=story&page={page}&hitsPerPage={per_page}"
        result = await self.client.fetch(url)

        if not result.success or not result.content:
            logger.warning("hackernews_fetch_failed", status=result.status_code, page=page)
            return discovered

        try:
            data = json.loads(result.content)
            hits = data.get("hits", [])
        except Exception as json_err:
            logger.warning("hackernews_json_failed", error=str(json_err))
            return discovered

        selected_hits = hits[item_offset:] if item_offset < len(hits) else hits

        for item in selected_hits:
            if len(discovered) >= limit:
                break

            title = item.get("title", "").strip()
            article_url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
            created_at_s = item.get("created_at")

            if not title or not article_url:
                continue

            # Parse datetime
            pub_date = datetime.now(timezone.utc)
            if created_at_s:
                try:
                    iso_str = created_at_s.replace("Z", "+00:00")
                    pub_date = datetime.fromisoformat(iso_str)
                except Exception:
                    pass

            raw_text = item.get("story_text") or title
            full_text = extract_clean_text(raw_text) or title

            article = RawNewsArticle(
                title=title,
                url=article_url,
                published_date=pub_date,
                full_text=full_text,
                source_name=self.source_name,
                source_url=self.source_url,
            )

            if qualify_news_article(article):
                discovered.append(article)

        return discovered
