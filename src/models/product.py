"""Product canonical data model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.models.base import CanonicalBase, Source
from src.models.enums import PricingModel


class ProductContent(CanonicalBase):
    """Content payload for a product record."""

    startupName: str = Field(
        ..., min_length=1, description="Name of the associated startup."
    )
    pricingModel: PricingModel | None = Field(
        default=None,
        description="Pricing model. None when unavailable.",
    )


class Product(CanonicalBase):
    """Canonical product record.

    Example::

        product = Product(
            source={"name": "Product Hunt", "url": "https://producthunt.com/posts/example"},
            content={"startupName": "Acme AI", "pricingModel": "FREEMIUM"},
            collectedAt="2026-08-15T12:00:00Z",
        )
    """

    schemaVersion: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    recordType: Literal["PRODUCT"] = "PRODUCT"
    source: Source
    content: ProductContent
    collectedAt: datetime
