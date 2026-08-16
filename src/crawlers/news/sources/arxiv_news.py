"""arXiv AI Research REST API news source."""

from __future__ import annotations

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from src.crawlers.news.models import RawNewsArticle
from src.crawlers.news.parser import extract_clean_text
from src.crawlers.news.qualifier import qualify_news_article
from src.crawlers.news.sources.base import BaseNewsSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

ARXIV_NEWS_API = (
    "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.CV"
)


class ArXivNewsSource(BaseNewsSource):
    """Discovers AI research news announcements from arXiv public REST API."""

    source_key = "arxiv"
    source_name = "arXiv AI News"
    source_url = "https://arxiv.org"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawNewsArticle]:
        discovered: list[RawNewsArticle] = []
        max_results = min(max(limit * 2, 20), 100)

        url = (
            f"{ARXIV_NEWS_API}&start={offset}&max_results={max_results}"
            "&sortBy=submittedDate&sortOrder=descending"
        )
        result = await self.client.fetch(url)

        if not result.success or not result.content:
            logger.warning("arxiv_news_fetch_failed", status=result.status_code)
            return discovered

        try:
            root = ET.fromstring(result.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                if len(discovered) >= limit:
                    break

                title_el = entry.find("atom:title", ns)
                id_el = entry.find("atom:id", ns)
                pub_el = entry.find("atom:published", ns)
                sum_el = entry.find("atom:summary", ns)

                title = (
                    title_el.text.strip().replace("\n", " ")
                    if title_el is not None and title_el.text
                    else ""
                )
                article_url = id_el.text.strip() if id_el is not None and id_el.text else ""
                summary = (
                    sum_el.text.strip().replace("\n", " ")
                    if sum_el is not None and sum_el.text
                    else title
                )

                if not title or not article_url:
                    continue

                pub_date = datetime.now(timezone.utc)
                if pub_el is not None and pub_el.text:
                    try:
                        pub_date = datetime.fromisoformat(pub_el.text.replace("Z", "+00:00"))
                    except Exception:
                        pass

                full_text = extract_clean_text(summary) or title

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

        except Exception as err:
            logger.warning("arxiv_news_parse_failed", error=str(err))

        return discovered
