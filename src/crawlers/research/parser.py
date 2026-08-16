"""ArXiv Atom XML feed parser for research paper extraction."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Sequence
import defusedxml.ElementTree as ET

from src.crawlers.research.models import RawPaper
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Atom feed namespace map
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivParser:
    """Parses arXiv Atom XML search responses into RawPaper records."""

    @classmethod
    def parse_feed(cls, xml_content: str) -> list[RawPaper]:
        """Parse XML feed string and return a list of RawPaper items."""
        if not xml_content or not xml_content.strip():
            return []

        try:
            root = ET.fromstring(xml_content.strip())
        except ET.ParseError as err:
            logger.error("arxiv_xml_parse_error", error=str(err))
            return []

        # Support both namespaced and non-namespaced entry tags
        entries = root.findall("atom:entry", NAMESPACES)
        if not entries:
            entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        if not entries:
            entries = root.findall("entry")

        papers: list[RawPaper] = []
        for entry in entries:
            paper = cls._parse_entry(entry)
            if paper and paper.title and paper.paper_url:
                papers.append(paper)

        logger.info("arxiv_feed_parsed", paper_count=len(papers))
        return papers

    @classmethod
    def _parse_entry(cls, entry: ET.Element) -> RawPaper | None:
        """Extract a RawPaper instance from an Atom <entry> element."""
        # Title
        title_elem = cls._find_tag(entry, "title")
        if title_elem is None or not title_elem.text:
            return None
        title = cls._clean_text(title_elem.text)

        # Paper URL
        id_elem = cls._find_tag(entry, "id")
        raw_url = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
        paper_url = cls._normalize_arxiv_url(raw_url)
        if not paper_url:
            return None

        # Summary / Abstract
        summary_elem = cls._find_tag(entry, "summary")
        summary = (
            cls._clean_text(summary_elem.text)
            if summary_elem is not None and summary_elem.text
            else ""
        )

        # Authors
        authors: list[str] = []
        author_elems = cls._find_all_tags(entry, "author")
        for auth_elem in author_elems:
            name_elem = cls._find_tag(auth_elem, "name")
            if name_elem is not None and name_elem.text:
                authors.append(cls._clean_text(name_elem.text))

        # Publication date
        pub_elem = cls._find_tag(entry, "published")
        pub_date = (
            cls._parse_date(pub_elem.text.strip())
            if pub_elem is not None and pub_elem.text
            else None
        )

        return RawPaper(
            title=title,
            authors=authors,
            paper_url=paper_url,
            summary=summary,
            published_date=pub_date or datetime.now(timezone.utc),
            source_name="arXiv",
            source_url="http://export.arxiv.org/api/query",
        )

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize whitespace and newlines inside XML text nodes."""
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_arxiv_url(url: str) -> str:
        """Convert raw arXiv ID/URL to canonical HTTPS URL format."""
        if not url:
            return ""
        # Handle arXiv ID format like http://arxiv.org/abs/2103.14030v1 -> https://arxiv.org/abs/2103.14030
        url = url.replace("http://", "https://")
        # Strip version suffix (e.g. v1, v2) if present
        url = re.sub(r"v\d+$", "", url)
        if not url.startswith("http"):
            url = f"https://arxiv.org/abs/{url}"
        return url

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Parse ISO-8601 publication date from Atom feed."""
        if not date_str:
            return None
        try:
            # e.g., 2021-03-25T17:59:00Z
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
        except ValueError:
            logger.warning("invalid_published_date", date_str=date_str)
            return None

    @staticmethod
    def _find_tag(element: ET.Element, tag_name: str) -> ET.Element | None:
        """Find child tag ignoring namespace."""
        for child in element:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == tag_name:
                return child
        return None

    @staticmethod
    def _find_all_tags(element: ET.Element, tag_name: str) -> list[ET.Element]:
        """Find all child tags ignoring namespace."""
        matches: list[ET.Element] = []
        for child in element:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == tag_name:
                matches.append(child)
        return matches
