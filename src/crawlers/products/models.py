"""Data models for raw product crawler payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from src.models.enums import PricingModel


@dataclass
class RawProduct:
    """Raw product payload object extracted by ProductParser."""

    product_name: str
    startup_name: str
    source_url: str
    source_name: str = "GitHub Products"
    pricing_model: PricingModel | None = None
    description: str | None = None
    is_qualified: bool = True
    qualification_category: str = "APPLICATION_TOOL"
    qualification_reasons: list[str] = field(default_factory=list)
    license_name: str | None = None
    pricing_reasons: list[str] = field(default_factory=list)
