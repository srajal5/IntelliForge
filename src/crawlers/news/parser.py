"""Parser for News RSS/Atom feeds and article text extraction."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import email.utils
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any

from defusedxml import ElementTree as ET

from src.crawlers.news.models import RawNewsArticle
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ArticleTextExtractor(HTMLParser):
    """HTML parser to extract clean readable text from HTML document body."""

    def __init__(self) -> None:
        super().__init__()
        self._text_chunks: list[str] = []
        self._ignore_tags = {
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "svg",
            "noscript",
            "head",
            "title",
            "iframe",
        }
        self._current_tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._current_tag_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        if self._current_tag_stack and self._current_tag_stack[-1] == tag.lower():
            self._current_tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if any(ignored in self._current_tag_stack for ignored in self._ignore_tags):
            return
        cleaned = data.strip()
        if cleaned:
            self._text_chunks.append(cleaned)

    def get_text(self) -> str:
        text = " ".join(self._text_chunks)
        text = unescape(text)
        # Collapse multiple spaces
        return re.sub(r"\s+", " ", text).strip()


def extract_clean_text(html_content: str | None) -> str | None:
    """Extract clean body text from HTML, removing script, style, and navigation tags."""
    if not html_content or not html_content.strip():
        return None

    try:
        parser = ArticleTextExtractor()
        parser.feed(html_content)
        extracted = parser.get_text()
        if len(extracted) >= 30:
            return extracted
    except Exception as exc:
        logger.debug("clean_text_extraction_error", error=str(exc))

    # Fallback regex strip if parser fails
    stripped = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    stripped = re.sub(r"\s+", " ", unescape(stripped)).strip()
    return stripped if len(stripped) >= 30 else None


def parse_pub_date_utc(date_str: str | None) -> datetime | None:
    """Parse RSS/Atom publication date string into timezone-aware UTC datetime.

    Returns None if publication date cannot be reliably determined.
    Never uses collection time as fallback.
    """
    if not date_str or not str(date_str).strip():
        return None

    cleaned = str(date_str).strip()

    # Try RFC 822 format (e.g. Wed, 15 Aug 2026 12:00:00 +0000)
    try:
        dt = email.utils.parsedate_to_datetime(cleaned)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
    except Exception:
        pass

    # Try ISO 8601 format
    try:
        iso_str = cleaned.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        pass

    return None


def is_news_fresh(
    pub_date: datetime | str | None,
    ref_time: datetime | None = None,
    max_age_hours: float = 24.0,
) -> tuple[bool, str]:
    """Check if publication timestamp is timezone-aware UTC and satisfies:
    published_at >= ref_time - max_age_hours.

    Returns tuple of (is_fresh: bool, status: str) where status is one of:
    'fresh', 'stale', 'missing_date', 'invalid_date'.
    """
    if pub_date is None:
        return False, "missing_date"

    if isinstance(pub_date, str):
        parsed = parse_pub_date_utc(pub_date)
        if parsed is None:
            return False, "invalid_date"
        pub_dt = parsed
    elif isinstance(pub_date, datetime):
        if pub_date.tzinfo is None:
            pub_dt = pub_date.replace(tzinfo=timezone.utc)
        else:
            pub_dt = pub_date.astimezone(timezone.utc)
    else:
        return False, "invalid_date"

    reference = ref_time if ref_time is not None else datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    cutoff = reference - timedelta(hours=max_age_hours)
    if pub_dt < cutoff:
        return False, "stale"

    return True, "fresh"


def parse_pub_date(date_str: str | None) -> datetime:
    """Parse RSS/Atom publication date string into timezone-aware datetime."""
    parsed = parse_pub_date_utc(date_str)
    if parsed is not None:
        return parsed
    return datetime.now(timezone.utc)


def parse_news_rss(
    xml_content: str | bytes,
    default_source_name: str | None = None,
    default_source_url: str | None = None,
) -> list[RawNewsArticle]:
    """Parse RSS 2.0 or Atom XML feed into list of RawNewsArticle models."""
    articles: list[RawNewsArticle] = []

    if isinstance(xml_content, str):
        xml_content = xml_content.encode("utf-8")

    if not xml_content or not xml_content.strip():
        return articles

    try:
        root = ET.fromstring(xml_content)
    except Exception as exc:
        logger.warning("xml_parse_failed", error=str(exc))
        return articles

    # Determine RSS vs Atom
    tag_name = root.tag.lower()

    if "rss" in tag_name or root.find("channel") is not None:
        channel = root.find("channel")
        if channel is None:
            return articles

        feed_title_node = channel.find("title")
        feed_link_node = channel.find("link")
        inferred_name = feed_title_node.text.strip() if feed_title_node is not None and feed_title_node.text else "RSS Feed"
        inferred_url = feed_link_node.text.strip() if feed_link_node is not None and feed_link_node.text else "https://techcrunch.com/"

        source_name = default_source_name or inferred_name
        source_url = default_source_url or inferred_url

        for item in channel.findall("item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            pub_date_elem = item.find("pubDate")
            desc_elem = item.find("description")

            # Namespaced content:encoded fallback
            content_encoded = None
            for child in item:
                if child.tag.endswith("encoded"):
                    content_encoded = child.text
                    break

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            pub_date_str = pub_date_elem.text.strip() if pub_date_elem is not None and pub_date_elem.text else ""

            if not title or not link:
                continue

            pub_date = parse_pub_date(pub_date_str)
            raw_text = content_encoded or (desc_elem.text if desc_elem is not None else None)
            full_text = extract_clean_text(raw_text)

            articles.append(
                RawNewsArticle(
                    title=title,
                    url=link,
                    published_date=pub_date,
                    full_text=full_text,
                    source_name=source_name,
                    source_url=source_url,
                )
            )

    elif "feed" in tag_name:  # Atom
        source_name_elem = root.find("{http://www.w3.org/2005/Atom}title")
        inferred_name = source_name_elem.text.strip() if source_name_elem is not None and source_name_elem.text else "Atom Feed"

        source_name = default_source_name or inferred_name
        source_url = default_source_url or "https://techcrunch.com/"

        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
            pub_elem = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")
            content_elem = entry.find("{http://www.w3.org/2005/Atom}content") or entry.find("{http://www.w3.org/2005/Atom}summary")

            link = ""
            for link_node in entry.findall("{http://www.w3.org/2005/Atom}link"):
                rel = link_node.attrib.get("rel", "alternate")
                if rel == "alternate" or not link:
                    link = link_node.attrib.get("href", "")

            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            pub_date_str = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

            if not title or not link:
                continue

            pub_date = parse_pub_date(pub_date_str)
            raw_text = content_elem.text if content_elem is not None else None
            full_text = extract_clean_text(raw_text)

            articles.append(
                RawNewsArticle(
                    title=title,
                    url=link,
                    published_date=pub_date,
                    full_text=full_text,
                    source_name=source_name,
                    source_url=source_url,
                )
            )

    return articles
