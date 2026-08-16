"""Parser for converting raw organization/startup payload items into RawStartup records."""

from __future__ import annotations

import re
from typing import Any

from src.crawlers.startups.models import RawStartup
from src.crawlers.startups.qualifier import StartupQualifier
from src.utils.logging import get_logger

logger = get_logger(__name__)

EMPLOYEE_REGEX = re.compile(
    r"(\d{1,6})\+?\s*(?:employees|people|team members|staff)",
    re.IGNORECASE,
)


class StartupParser:
    """Parses raw JSON organization items into RawStartup instances."""

    @classmethod
    def parse_item(cls, item: dict[str, Any]) -> RawStartup | None:
        """Parse a single organization dictionary into a RawStartup object."""
        if not isinstance(item, dict):
            return None

        login = item.get("login", "").strip()
        name = item.get("name", "").strip() if item.get("name") else ""
        entity_name = name or login

        if not entity_name:
            logger.warning("startup_parse_missing_entity_name", item=item)
            return None

        html_url = item.get("html_url", "").strip()
        if not html_url and login:
            html_url = f"https://github.com/{login}"

        if not html_url or not html_url.startswith("http"):
            logger.warning("startup_parse_invalid_url", url=html_url, entity=entity_name)
            return None

        description = item.get("description", "") or ""
        employee_count = cls._extract_employee_count(description)

        # Qualify organization based on explicit evidence
        qualification = StartupQualifier.qualify(item)

        return RawStartup(
            entity_name=entity_name,
            source_url=html_url,
            source_name="GitHub Organizations",
            employee_count=employee_count,
            description=description if description else None,
            is_qualified=qualification.is_qualified,
            qualification_category=qualification.category,
            qualification_reasons=qualification.reasons,
        )

    @classmethod
    def parse_items(cls, items: list[dict[str, Any]]) -> list[RawStartup]:
        """Parse a list of raw organization items."""
        startups: list[RawStartup] = []
        for item in items:
            parsed = cls.parse_item(item)
            if parsed:
                startups.append(parsed)
        return startups

    @staticmethod
    def _extract_employee_count(text: str) -> int | None:
        """Extract employee count integer strictly from explicit textual phrases.

        Do NOT infer employee count from follower counts, member counts, or star counts.
        """
        if not text or not isinstance(text, str):
            return None
        match = EMPLOYEE_REGEX.search(text)
        if match:
            try:
                val = int(match.group(1))
                if val >= 0:
                    return val
            except ValueError:
                pass
        return None
