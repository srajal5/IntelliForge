"""Unit tests for StartupQualifier evidence and classification layer."""

import pytest
from src.crawlers.startups.qualifier import StartupQualifier


def test_qualify_startup_with_company_keyword():
    item = {
        "login": "acme-ai",
        "name": "Acme AI Inc",
        "description": "An AI company building foundation models",
        "blog": "https://acme.ai",
    }
    result = StartupQualifier.qualify(item)
    assert result.is_qualified is True
    assert result.category == "STARTUP_COMPANY"
    assert any("company" in r for r in result.reasons)


def test_qualify_startup_with_external_domain():
    item = {
        "login": "deepmind-labs",
        "name": "DeepMind Labs",
        "description": "Frontier AI research and products",
        "blog": "https://deepmind.com",
    }
    result = StartupQualifier.qualify(item)
    assert result.is_qualified is True
    assert result.category == "STARTUP_COMPANY"
    assert any("domain" in r for r in result.reasons)


def test_qualify_open_source_community_no_startup_evidence():
    item = {
        "login": "TheAlgorithms",
        "name": "The Algorithms",
        "description": "Open source resource for algorithms in Python and Java",
        "blog": "",
    }
    result = StartupQualifier.qualify(item)
    assert result.is_qualified is False
    assert result.category in ("OPEN_SOURCE_COMMUNITY", "UNKNOWN")


def test_qualify_educational_university():
    item = {
        "login": "stanford-ai",
        "name": "Stanford AI Lab",
        "description": "University research group studying machine learning",
        "blog": "https://ai.stanford.edu",
    }
    result = StartupQualifier.qualify(item)
    assert result.is_qualified is False
    assert result.category == "EDUCATIONAL"


def test_qualify_unknown_no_evidence():
    item = {
        "login": "random-org-123",
        "name": "",
        "description": "",
        "blog": "",
    }
    result = StartupQualifier.qualify(item)
    assert result.is_qualified is False
    assert result.category == "UNKNOWN"
