"""Tests for the Product canonical model."""

import pytest
from pydantic import ValidationError

from src.models.product import Product


# ------------------------------------------------------------------
# Valid fixtures
# ------------------------------------------------------------------

def _valid_product_data() -> dict:
    return {
        "source": {"name": "Product Hunt", "url": "https://producthunt.com/posts/acme"},
        "content": {"startupName": "Acme AI", "pricingModel": "FREEMIUM"},
        "collectedAt": "2026-08-15T12:00:00Z",
    }


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


def test_valid_product():
    p = Product(**_valid_product_data())
    assert p.recordType == "PRODUCT"
    assert p.content.pricingModel.value == "FREEMIUM"


def test_valid_product_all_pricing_models():
    for pm in ("FREE", "FREEMIUM", "PAID", "ENTERPRISE"):
        data = _valid_product_data()
        data["content"]["pricingModel"] = pm
        p = Product(**data)
        assert p.content.pricingModel.value == pm


def test_valid_product_no_pricing():
    data = _valid_product_data()
    data["content"]["pricingModel"] = None
    p = Product(**data)
    assert p.content.pricingModel is None


def test_product_json_serialization():
    p = Product(**_valid_product_data())
    d = p.to_dict()
    assert d["recordType"] == "PRODUCT"
    assert d["content"]["pricingModel"] == "FREEMIUM"

    json_str = p.to_json()
    assert '"PRODUCT"' in json_str
    assert '"FREEMIUM"' in json_str


# ------------------------------------------------------------------
# Invalid cases
# ------------------------------------------------------------------


def test_invalid_pricing_model():
    data = _valid_product_data()
    data["content"]["pricingModel"] = "CHEAP"
    with pytest.raises(ValidationError, match="pricingModel"):
        Product(**data)


def test_invalid_pricing_model_random_string():
    data = _valid_product_data()
    data["content"]["pricingModel"] = "subscription"
    with pytest.raises(ValidationError, match="pricingModel"):
        Product(**data)


def test_invalid_source_url():
    data = _valid_product_data()
    data["source"]["url"] = "not-a-url"
    with pytest.raises(ValidationError, match="url"):
        Product(**data)


def test_invalid_record_type():
    data = _valid_product_data()
    data["recordType"] = "STARTUP"
    with pytest.raises(ValidationError, match="recordType"):
        Product(**data)


def test_missing_startup_name():
    data = _valid_product_data()
    del data["content"]["startupName"]
    with pytest.raises(ValidationError, match="startupName"):
        Product(**data)


def test_invalid_collected_at():
    data = _valid_product_data()
    data["collectedAt"] = "yesterday"
    with pytest.raises(ValidationError, match="collectedAt"):
        Product(**data)
