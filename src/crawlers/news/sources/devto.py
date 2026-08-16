"""DEV.to AI tag public REST API news source."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.crawlers.news.models import RawNewsArticle
from src.crawlers.news.parser import extract_clean_text
from src.crawlers.news.qualifier import qualify_news_article
from src.crawlers.news.sources.base import BaseNewsSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEVTO_ARTICLES_API = "https://dev.to/api/articles"


class DEVtoAISource(BaseNewsSource):
    """Discovers AI tech articles from DEV.to public API."""

    source_key = "devto"
    source_name = "DEV.to AI"
    source_url = "https://dev.to/t/ai"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawNewsArticle]:
        discovered: list[RawNewsArticle] = []
        per_page = 50
        page = (offset // per_page) + 1
        item_offset = offset % per_page

        url = f"{DEVTO_ARTICLES_API}?tag=ai&per_page={per_page}&page={page}"
        result = await self.client.fetch(url)

        if not result.success or not result.content:
            logger.warning("devto_fetch_failed", status=result.status_code, page=page)
            return discovered

        try:
            items = json.loads(result.content)
            if not isinstance(items, list):
                return discovered
        except Exception as json_err:
            logger.warning("devto_json_failed", error=str(json_err))
            return discovered

        selected = items[item_offset:] if item_offset < len(items) else items

        for item in selected:
            if len(discovered) >= limit:
                break

            title = (item.get("title") or "").strip()
            article_url = item.get("url") or item.get("canonical_url")
            pub_date_s = item.get("published_at") or item.get("created_at")

            if not title or not article_url:
                continue

            pub_date = datetime.now(timezone.utc)
            if pub_date_s:
                try:
                    iso_str = pub_date_s.replace("Z", "+00:00")
                    pub_date = datetime.fromisoformat(iso_str)
                except Exception:
                    pass

            desc = item.get("description") or title
            full_text = extract_clean_text(desc) or title

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
