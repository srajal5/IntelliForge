"""Qualification and classification layer for Startup organizations."""

from __future__ import annotations

import re
from typing import Any, NamedTuple
from urllib.parse import urlparse


class QualificationResult(NamedTuple):
    """Result of evaluating source evidence for a startup/company record."""

    is_qualified: bool
    category: str
    reasons: list[str]


FOUNDATION_KEYWORDS = {
    "non-profit",
    "nonprofit",
    "association",
    "consortium",
}

COMPANY_KEYWORDS = {
    "inc",
    "corp",
    "corporation",
    "ltd",
    "limited",
    "llc",
    "gmbh",
    "company",
    "startup",
    "ai company",
    "tech company",
    "software company",
    "official github for",
    "commercial",
    "enterprise",
    "platform provider",
    "solution provider",
    "building",
}

COMMUNITY_KEYWORDS = {
    "open source community",
    "collection of algorithms",
    "algorithms",
    "curated list",
    "community-driven",
    "open-source resource",
}

EDUCATIONAL_KEYWORDS = {
    "university",
    "college",
    "school",
    "research lab",
    "academic",
    "institute of technology",
}


def _is_custom_domain(blog_url: str) -> bool:
    """Check if blog URL represents a custom corporate/startup domain rather than blog host."""
    url = blog_url if blog_url.startswith("http") else f"https://{blog_url}"
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    ignored_hosts = ("github.io", "blogspot.com", "wordpress.com", "medium.com")
    for ignored in ignored_hosts:
        if host == ignored or host.endswith(f".{ignored}"):
            return False
    return True


class StartupQualifier:
    """Evaluates raw GitHub organization metadata to establish startup/company evidence."""

    @classmethod
    def qualify(cls, item: dict[str, Any]) -> QualificationResult:
        """Classify a raw GitHub organization item based on text and metadata evidence."""
        reasons: list[str] = []
        name = (item.get("name") or item.get("login") or "").strip()
        description = (item.get("description") or "").strip().lower()
        blog = (item.get("blog") or "").strip().lower()
        email = (item.get("email") or "").strip().lower()

        # Check educational evidence
        if any(kw in description for kw in EDUCATIONAL_KEYWORDS) or ".edu" in blog or ".edu" in email:
            reasons.append("Matches educational or university patterns")
            return QualificationResult(
                is_qualified=False,
                category="EDUCATIONAL",
                reasons=reasons,
            )

        # Check foundation/nonprofit evidence (excluding "foundation model")
        is_nonprofit_foundation = False
        if any(kw in description for kw in FOUNDATION_KEYWORDS):
            is_nonprofit_foundation = True
        elif re.search(r"\bfoundation\b(?!\s*models?)", description):
            is_nonprofit_foundation = True

        if is_nonprofit_foundation:
            reasons.append("Matches foundation/nonprofit keywords in description")
            return QualificationResult(
                is_qualified=False,
                category="FOUNDATION_NONPROFIT",
                reasons=reasons,
            )

        # Check community evidence
        if any(kw in description for kw in COMMUNITY_KEYWORDS):
            reasons.append("Matches open-source community/resource keywords")
            return QualificationResult(
                is_qualified=False,
                category="OPEN_SOURCE_COMMUNITY",
                reasons=reasons,
            )

        # Check company/startup evidence
        company_evidence = False
        name_lower = name.lower()

        for kw in COMPANY_KEYWORDS:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, description) or re.search(pattern, name_lower):
                company_evidence = True
                reasons.append(f"Contains company keyword '{kw}'")

        if blog and _is_custom_domain(blog):
            company_evidence = True
            reasons.append(f"Has official external domain '{blog}'")

        if company_evidence:
            return QualificationResult(
                is_qualified=True,
                category="STARTUP_COMPANY",
                reasons=reasons,
            )

        # Fallback if no explicit startup evidence exists
        reasons.append("Insufficient evidence to reliably establish startup/company status")
        return QualificationResult(
            is_qualified=False,
            category="UNKNOWN",
            reasons=reasons,
        )
