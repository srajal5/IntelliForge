"""Unit tests for modular news source adapters."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.crawlers.news.sources.hackernews import HackerNewsSource
from src.crawlers.news.sources.kdnuggets import KDnuggetsSource
from src.crawlers.news.sources.mit_tech_review import MITTechReviewSource
from src.crawlers.news.sources.venturebeat import VentureBeatSource


@pytest.mark.asyncio
async def test_hackernews_source():
    mock_client = AsyncMock()
    hn_payload = {
        "hits": [
            {
                "objectID": "12345",
                "title": "OpenAI Releases New Frontier AI Model",
                "url": "https://news.ycombinator.com/item?id=12345",
                "created_at": "2026-08-16T10:00:00Z",
                "story_text": "Discussion on frontier AI model release.",
            }
        ]
    }
    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=json.dumps(hn_payload),
    )

    source = HackerNewsSource(client=mock_client)
    articles = await source.discover(limit=5, offset=0)

    assert len(articles) == 1
    assert articles[0].title == "OpenAI Releases New Frontier AI Model"
    assert articles[0].source_name == "Hacker News AI"


@pytest.mark.asyncio
async def test_venturebeat_source():
    mock_client = AsyncMock()
    rss_data = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>VentureBeat AI</title>
        <link>https://venturebeat.com/category/ai/</link>
        <item>
          <title>AI Enterprise Chip Breakthrough Announced</title>
          <link>https://venturebeat.com/ai/enterprise-chip/</link>
          <pubDate>Sun, 16 Aug 2026 09:00:00 +0000</pubDate>
          <description>Enterprise chip for AI models.</description>
        </item>
      </channel>
    </rss>"""

    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=rss_data,
    )

    source = VentureBeatSource(client=mock_client)
    articles = await source.discover(limit=5, offset=0)

    assert len(articles) == 1
    assert articles[0].title == "AI Enterprise Chip Breakthrough Announced"
    assert articles[0].source_name == "VentureBeat AI"


@pytest.mark.asyncio
async def test_mit_tech_review_source():
    mock_client = AsyncMock()
    rss_data = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>MIT Technology Review AI</title>
        <link>https://www.technologyreview.com</link>
        <item>
          <title>The Future of Autonomous AI Agents in Healthcare</title>
          <link>https://www.technologyreview.com/2026/08/16/ai-agents-healthcare/</link>
          <pubDate>Sun, 16 Aug 2026 08:00:00 +0000</pubDate>
          <description>Exploring autonomous AI agents.</description>
        </item>
      </channel>
    </rss>"""

    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=rss_data,
    )

    source = MITTechReviewSource(client=mock_client)
    articles = await source.discover(limit=5, offset=0)

    assert len(articles) == 1
    assert articles[0].title == "The Future of Autonomous AI Agents in Healthcare"
    assert articles[0].source_name == "MIT Technology Review AI"


@pytest.mark.asyncio
async def test_devto_source():
    from src.crawlers.news.sources.devto import DEVtoAISource

    mock_client = AsyncMock()
    devto_payload = [
        {
            "id": 9999,
            "title": "Building Autonomous AI Agents with Python",
            "url": "https://dev.to/user/building-autonomous-ai-agents",
            "published_at": "2026-08-16T10:00:00Z",
            "description": "Comprehensive guide on building autonomous AI agents in Python.",
        }
    ]
    mock_client.fetch.return_value = MagicMock(
        success=True,
        status_code=200,
        content=json.dumps(devto_payload),
    )

    source = DEVtoAISource(client=mock_client)
    articles = await source.discover(limit=5, offset=0)

    assert len(articles) == 1
    assert articles[0].title == "Building Autonomous AI Agents with Python"
    assert articles[0].source_name == "DEV.to AI"
