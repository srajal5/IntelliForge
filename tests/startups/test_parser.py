"""Tests for StartupParser."""

import pytest
from src.crawlers.startups.parser import StartupParser


def test_parse_valid_startup():
    item = {
        "login": "openai",
        "name": "OpenAI",
        "html_url": "https://github.com/openai",
        "description": "AI research company with 500 employees",
    }
    raw = StartupParser.parse_item(item)
    assert raw is not None
    assert raw.entity_name == "OpenAI"
    assert raw.source_url == "https://github.com/openai"
    assert raw.employee_count == 500


def test_follower_count_does_not_become_employee_count():
    """Verify that GitHub followers or member counts are NOT converted into employee count."""
    item = {
        "login": "popular-org",
        "name": "Popular Org",
        "html_url": "https://github.com/popular-org",
        "description": "Popular open source organization",
        "followers": 15000,
        "public_repos": 200,
        "members_count": 50,
    }
    raw = StartupParser.parse_item(item)
    assert raw is not None
    assert raw.employee_count is None, "Follower count must NOT be used as employee count"


def test_parse_startup_using_login_when_name_missing():
    item = {
        "login": "anthropic",
        "html_url": "https://github.com/anthropic",
        "description": "AI safety company",
    }
    raw = StartupParser.parse_item(item)
    assert raw is not None
    assert raw.entity_name == "anthropic"
    assert raw.employee_count is None


def test_parse_startup_missing_employee_count():
    item = {
        "login": "supabase",
        "html_url": "https://github.com/supabase",
        "description": "The Open Source Firebase Alternative",
    }
    raw = StartupParser.parse_item(item)
    assert raw is not None
    assert raw.employee_count is None


def test_parse_startup_invalid_url():
    item = {
        "login": "invalid",
        "html_url": "not-a-url",
    }
    raw = StartupParser.parse_item(item)
    assert raw is None


def test_parse_startup_missing_entity_name():
    item = {
        "login": "",
        "name": "",
        "html_url": "https://github.com/something",
    }
    raw = StartupParser.parse_item(item)
    assert raw is None


def test_parse_items_list():
    items = [
        {"login": "s1", "html_url": "https://github.com/s1"},
        {"login": "s2", "html_url": "https://github.com/s2"},
    ]
    raws = StartupParser.parse_items(items)
    assert len(raws) == 2
    assert raws[0].entity_name == "s1"
    assert raws[1].entity_name == "s2"
