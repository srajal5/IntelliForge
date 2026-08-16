"""Unit tests for ProductQualifier evidence and classification layer."""

import pytest
from src.crawlers.products.qualifier import ProductQualifier


def test_qualify_application_product():
    item = {
        "name": "dify",
        "description": "An open-source LLM application development platform",
        "topics": ["llm", "ai", "platform"],
    }
    result = ProductQualifier.qualify(item)
    assert result.is_qualified is True
    assert result.category in ("SAAS_PRODUCT", "APPLICATION_TOOL")


def test_qualify_educational_tutorial_repo():
    item = {
        "name": "JavaGuide",
        "description": "Java interview guide and study resource",
        "topics": ["java", "interview"],
    }
    result = ProductQualifier.qualify(item)
    assert result.is_qualified is False
    assert result.category == "EDUCATIONAL_TUTORIAL"


def test_qualify_general_library_framework():
    item = {
        "name": "superpowers",
        "description": "Agent framework for workflow orchestration",
        "topics": ["agents"],
    }
    result = ProductQualifier.qualify(item)
    assert result.is_qualified is True
    assert result.category in ("LIBRARY_FRAMEWORK", "APPLICATION_TOOL")
