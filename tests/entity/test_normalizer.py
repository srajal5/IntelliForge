"""Unit tests for entity normalizer."""

import pytest
from src.entity.normalizer import normalize_entity_name


def test_normalize_basic_lowercase():
    assert normalize_entity_name("OPENAI") == "openai"
    assert normalize_entity_name("  OpenAI  ") == "openai"


def test_normalize_corporate_suffixes():
    assert normalize_entity_name("OpenAI, Inc.") == "openai"
    assert normalize_entity_name("OpenAI Inc") == "openai"
    assert normalize_entity_name("Anthropic PBC") == "anthropic"
    assert normalize_entity_name("Microsoft Corporation") == "microsoft"
    assert normalize_entity_name("Acme Ltd.") == "acme"
    assert normalize_entity_name("Widgets LLC") == "widgets"
    assert normalize_entity_name("Tech GmbH") == "tech"


def test_normalize_urls_and_domains():
    assert normalize_entity_name("openai.com") == "openai"
    assert normalize_entity_name("https://openai.com") == "openai"
    assert normalize_entity_name("https://github.com/openai") == "openai"


def test_normalize_preserve_meaningful_words():
    # Should NOT strip 'ai' or 'labs' from the middle or end of proper names
    assert normalize_entity_name("OpenAI") == "openai"
    assert normalize_entity_name("DeepMind Labs") == "deepmind labs"
    assert normalize_entity_name("Google DeepMind") == "google deepmind"


def test_normalize_unicode_and_punctuation():
    assert normalize_entity_name("Café AI, Inc.") == "cafe ai"
    assert normalize_entity_name("Open-AI (Inc.)") == "open ai"


def test_normalize_empty_or_invalid():
    assert normalize_entity_name("") == ""
    assert normalize_entity_name(None) == ""
