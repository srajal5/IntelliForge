"""Parser for converting raw product payload items into RawProduct records."""

from __future__ import annotations

import re
from typing import Any

from src.crawlers.products.models import RawProduct
from src.crawlers.products.qualifier import ProductQualifier
from src.models.enums import PricingModel
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProductParser:
    """Parses raw JSON repository/product items into RawProduct instances."""

    @classmethod
    def parse_item(cls, item: dict[str, Any]) -> RawProduct | None:
        """Parse a single repository dictionary into a RawProduct object."""
        if not isinstance(item, dict):
            return None

        product_name = item.get("name", "").strip()
        owner_obj = item.get("owner", {})
        startup_name = ""
        if isinstance(owner_obj, dict):
            startup_name = (owner_obj.get("login") or owner_obj.get("name") or "").strip()

        if not product_name or not startup_name:
            logger.warning("product_parse_missing_name_or_startup", product=product_name, startup=startup_name)
            return None

        source_url = item.get("html_url", "").strip()
        if not source_url or not source_url.startswith("http"):
            logger.warning("product_parse_invalid_url", url=source_url, product=product_name)
            return None

        description = item.get("description", "") or ""
        license_obj = item.get("license") or {}
        license_key = license_obj.get("key", "").lower() if isinstance(license_obj, dict) else ""
        license_name = license_obj.get("name") if isinstance(license_obj, dict) else None

        pricing, pricing_reasons = cls._determine_pricing(description)
        qualification = ProductQualifier.qualify(item)

        return RawProduct(
            product_name=product_name,
            startup_name=startup_name,
            source_url=source_url,
            source_name="GitHub Products",
            pricing_model=pricing,
            description=description if description else None,
            is_qualified=qualification.is_qualified,
            qualification_category=qualification.category,
            qualification_reasons=qualification.reasons,
            license_name=license_name or license_key or None,
            pricing_reasons=pricing_reasons,
        )

    @classmethod
    def parse_items(cls, items: list[dict[str, Any]]) -> list[RawProduct]:
        """Parse a list of raw product items."""
        products: list[RawProduct] = []
        for item in items:
            parsed = cls.parse_item(item)
            if parsed:
                products.append(parsed)
        return products

    @staticmethod
    def _determine_pricing(description: str) -> tuple[PricingModel | None, list[str]]:
        """Determine pricing model strictly based on explicit textual pricing evidence.

        CRITICAL: An open-source license (MIT, Apache-2.0, GPL, etc.) is LICENSE information,
        NOT pricing model information. Do NOT default open-source licensed repositories to FREE.
        """
        if not description or not isinstance(description, str):
            return None, ["No explicit description text provided"]

        desc_lower = description.lower()
        reasons: list[str] = []

        if "freemium" in desc_lower or "free tier" in desc_lower or "free community edition" in desc_lower:
            reasons.append("Explicit freemium / free tier statement in text")
            return PricingModel.FREEMIUM, reasons

        if "enterprise edition" in desc_lower or "contact sales" in desc_lower or "enterprise plan" in desc_lower:
            reasons.append("Explicit enterprise pricing indicator in text")
            return PricingModel.ENTERPRISE, reasons

        if "paid plan" in desc_lower or "paid subscription" in desc_lower or "commercial license required" in desc_lower or "$/mo" in desc_lower:
            reasons.append("Explicit paid pricing statement in text")
            return PricingModel.PAID, reasons

        if "100% free" in desc_lower or "free to use" in desc_lower or "completely free" in desc_lower or "free software (no cost)" in desc_lower:
            reasons.append("Explicit cost-free pricing statement in text")
            return PricingModel.FREE, reasons

        reasons.append("No explicit commercial pricing statements found in description (license information alone is not pricing)")
        return None, reasons
