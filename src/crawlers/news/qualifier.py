"""News article quality validation logic."""

from __future__ import annotations

from src.crawlers.news.models import RawNewsArticle


def qualify_news_article(article: RawNewsArticle) -> bool:
    """Validate that a news article record has required minimum fields."""
    if not article.title or not article.title.strip():
        return False
    if not article.url or not article.url.strip() or not article.url.startswith("http"):
        return False
    return True
