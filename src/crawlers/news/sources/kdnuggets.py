"""KDnuggets AI RSS news source."""

from __future__ import annotations

from src.crawlers.news.models import RawNewsArticle
from src.crawlers.news.parser import extract_clean_text, parse_news_rss
from src.crawlers.news.qualifier import qualify_news_article
from src.crawlers.news.sources.base import BaseNewsSource
from src.utils.logging import get_logger

logger = get_logger(__name__)


class KDnuggetsSource(BaseNewsSource):
    """Discovers news articles from KDnuggets RSS feed."""

    source_key = "kdnuggets"
    source_name = "KDnuggets AI"
    source_url = "https://www.kdnuggets.com"
    feed_url = "https://www.kdnuggets.com/feed"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawNewsArticle]:
        discovered: list[RawNewsArticle] = []
        result = await self.client.fetch(self.feed_url)
        if not result.success or not result.content:
            logger.warning("kdnuggets_fetch_failed", status=result.status_code)
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
            if not qualify_news_article(article):
                continue

            if not article.full_text or len(article.full_text) < 50:
                try:
                    art_resp = await self.client.fetch(article.url)
                    if art_resp.success and art_resp.content:
                        extracted = extract_clean_text(art_resp.content)
                        if extracted:
                            article.full_text = extracted
                except Exception as exc:
                    logger.debug("kdnuggets_full_text_error", url=article.url, error=str(exc))

            discovered.append(article)

        return discovered
