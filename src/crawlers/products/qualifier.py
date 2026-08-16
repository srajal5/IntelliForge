"""Qualification and classification layer for Product repositories."""

from __future__ import annotations

import re
from typing import Any, NamedTuple


class ProductQualificationResult(NamedTuple):
    """Result of evaluating source evidence for a product record."""

    is_qualified: bool
    category: str
    reasons: list[str]


EDUCATIONAL_LIST_KEYWORDS = {
    "interview guide",
    "study guide",
    "learning resource",
    "awesome list",
    "roadmap",
    "curated list of",
    "interview questions",
    "cheat sheet",
    "cheatsheet",
}

PRODUCT_KEYWORDS = {
    "application",
    "tool",
    "agent",
    "webui",
    "platform",
    "framework",
    "library",
    "system",
    "engine",
    "sdk",
    "cli",
    "saas",
    "product",
    "service",
    "copilot",
    "assistant",
}


class ProductQualifier:
    """Evaluates raw GitHub repository metadata to establish product evidence."""

    @classmethod
    def qualify(cls, item: dict[str, Any]) -> ProductQualificationResult:
        """Classify a raw GitHub repository item based on text and metadata evidence."""
        reasons: list[str] = []
        name = (item.get("name") or "").strip().lower()
        description = (item.get("description") or "").strip().lower()
        topics = item.get("topics") or []
        topics_str = " ".join(t.lower() for t in topics) if isinstance(topics, list) else ""

        full_text = f"{name} {description} {topics_str}"

        # Check educational / link aggregation repository evidence
        if any(kw in full_text for kw in EDUCATIONAL_LIST_KEYWORDS):
            reasons.append("Matches educational resource / interview guide pattern")
            return ProductQualificationResult(
                is_qualified=False,
                category="EDUCATIONAL_TUTORIAL",
                reasons=reasons,
            )

        # Check SaaS / application / tool / framework evidence
        found_keywords = []
        for kw in PRODUCT_KEYWORDS:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, full_text):
                found_keywords.append(kw)

        if found_keywords:
            reasons.append(f"Contains product/tool indicators: {', '.join(found_keywords[:3])}")
            category = "SAAS_PRODUCT" if "saas" in found_keywords else "APPLICATION_TOOL"
            return ProductQualificationResult(
                is_qualified=True,
                category=category,
                reasons=reasons,
            )

        # Default classification if repository exists but product context is ambiguous
        reasons.append("General software repository with developer/product utility")
        return ProductQualificationResult(
            is_qualified=True,
            category="LIBRARY_FRAMEWORK",
            reasons=reasons,
        )
