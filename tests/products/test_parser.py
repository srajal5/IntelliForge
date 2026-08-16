"""Tests for ProductParser including every PricingModel enum, strict license rules, and edge cases."""

import pytest
from src.crawlers.products.parser import ProductParser
from src.models.enums import PricingModel


def test_mit_license_does_not_automatically_become_free():
    """Verify that an MIT license key alone does NOT set pricing_model to FREE."""
    item = {
        "name": "AutoGPT",
        "owner": {"login": "Significant-Gravitas"},
        "html_url": "https://github.com/Significant-Gravitas/AutoGPT",
        "license": {"key": "mit"},
        "description": "An accessible AI tool for everyone",
    }
    raw = ProductParser.parse_item(item)
    assert raw is not None
    assert raw.product_name == "AutoGPT"
    assert raw.startup_name == "Significant-Gravitas"
    assert raw.source_url == "https://github.com/Significant-Gravitas/AutoGPT"
    assert raw.pricing_model is None, "MIT license key alone must not map to FREE"


def test_apache_license_does_not_automatically_become_free():
    """Verify that an Apache-2.0 license key alone does NOT set pricing_model to FREE."""
    item = {
        "name": "ApacheTool",
        "owner": {"login": "ApacheOrg"},
        "html_url": "https://github.com/ApacheOrg/ApacheTool",
        "license": {"key": "apache-2.0"},
        "description": "A developer framework",
    }
    raw = ProductParser.parse_item(item)
    assert raw is not None
    assert raw.pricing_model is None, "Apache-2.0 license key alone must not map to FREE"


def test_parse_product_explicit_free_text():
    """Explicit text stating cost-free software maps to FREE."""
    item = {
        "name": "FreeTool",
        "owner": {"login": "FreeDev"},
        "html_url": "https://github.com/FreeDev/FreeTool",
        "description": "100% free to use AI editor for all users",
    }
    raw = ProductParser.parse_item(item)
    assert raw is not None
    assert raw.pricing_model == PricingModel.FREE


def test_parse_product_pricing_freemium():
    item = {
        "name": "SuperTool",
        "owner": {"login": "AcmeCorp"},
        "html_url": "https://github.com/AcmeCorp/SuperTool",
        "description": "A freemium AI development framework with free tier",
    }
    raw = ProductParser.parse_item(item)
    assert raw is not None
    assert raw.pricing_model == PricingModel.FREEMIUM


def test_parse_product_pricing_paid():
    item = {
        "name": "PaidBot",
        "owner": {"login": "PaidInc"},
        "html_url": "https://github.com/PaidInc/PaidBot",
        "description": "Paid plan required for commercial use",
    }
    raw = ProductParser.parse_item(item)
    assert raw is not None
    assert raw.pricing_model == PricingModel.PAID


def test_parse_product_pricing_enterprise():
    item = {
        "name": "EnterpriseAgent",
        "owner": {"login": "BigCorp"},
        "html_url": "https://github.com/BigCorp/EnterpriseAgent",
        "description": "Enterprise edition suite, contact sales for pricing",
    }
    raw = ProductParser.parse_item(item)
    assert raw is not None
    assert raw.pricing_model == PricingModel.ENTERPRISE


def test_parse_product_missing_pricing():
    item = {
        "name": "MysteryTool",
        "owner": {"login": "UnknownGroup"},
        "html_url": "https://github.com/UnknownGroup/MysteryTool",
        "description": "Experimental repository",
    }
    raw = ProductParser.parse_item(item)
    assert raw is not None
    assert raw.pricing_model is None


def test_parse_product_missing_name_or_startup():
    item1 = {"name": "", "owner": {"login": "owner"}, "html_url": "https://github.com/owner/p"}
    item2 = {"name": "prod", "owner": {"login": ""}, "html_url": "https://github.com/owner/p"}

    assert ProductParser.parse_item(item1) is None
    assert ProductParser.parse_item(item2) is None


def test_parse_product_invalid_url():
    item = {
        "name": "prod",
        "owner": {"login": "owner"},
        "html_url": "ftp://invalid-scheme",
    }
    assert ProductParser.parse_item(item) is None


def test_parse_items_list():
    items = [
        {"name": "p1", "owner": {"login": "o1"}, "html_url": "https://github.com/o1/p1"},
        {"name": "p2", "owner": {"login": "o2"}, "html_url": "https://github.com/o2/p2"},
    ]
    raws = ProductParser.parse_items(items)
    assert len(raws) == 2
    assert raws[0].product_name == "p1"
    assert raws[1].product_name == "p2"
