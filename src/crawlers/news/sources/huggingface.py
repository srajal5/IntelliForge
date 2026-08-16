"""Hugging Face Blog RSS news source."""

from __future__ import annotations

from src.crawlers.news.models import RawNewsArticle
from src.crawlers.news.parser import extract_clean_text, parse_news_rss
from src.crawlers.news.qualifier import qualify_news_article
from src.crawlers.news.sources.base import BaseNewsSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

HF_BLOG_FEED = "https://huggingface.co/blog/feed.xml"


class HuggingFaceSource(BaseNewsSource):
    """Discovers AI research and engineering articles from Hugging Face Blog."""

    source_key = "huggingface"
    source_name = "Hugging Face Blog"
    source_url = "https://huggingface.co/blog"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawNewsArticle]:
        discovered: list[RawNewsArticle] = []
        result = await self.client.fetch(HF_BLOG_FEED)
        if not result.success or not result.content:
            logger.warning("huggingface_fetch_failed", status=result.status_code)
            return discovered

        articles = parse_news_rss(
            result.content,
            default_source_name=self.source_name,
            default_source_url=self.source_url,
        )
        selected = articles[offset:] if offset < len(articles) else []

        for article in selected:
            if len(discovered) >= limit:
                break
            if qualify_news_article(article):
                discovered.append(article)

        return discovered
