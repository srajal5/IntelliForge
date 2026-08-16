"""Unit tests for News ingestion vertical (Requirement 23)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.crawlers.news.adapter import NewsAdapter
from src.crawlers.news.models import RawNewsArticle
from src.crawlers.news.parser import (
    extract_clean_text,
    parse_news_rss,
    parse_pub_date,
)
from src.crawlers.news.qualifier import qualify_news_article
from src.models.news import News, NewsContent
from src.services.news import NewsService
from src.storage.repositories.news import NewsRepository

SAMPLE_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TechCrunch AI</title>
    <link>https://techcrunch.com/category/artificial-intelligence/</link>
    <description>Latest AI news</description>
    <item>
      <title>Startup Launches Next-Gen AI Model</title>
      <link>https://techcrunch.com/2026/08/15/ai-startup-model</link>
      <pubDate>Wed, 15 Aug 2026 12:00:00 +0000</pubDate>
      <description>&lt;p&gt;Startup XYZ has announced a groundbreaking new AI model.&lt;/p&gt;</description>
    </item>
    <item>
      <title>AI Safety Accord Signed</title>
      <link>https://techcrunch.com/2026/08/15/ai-safety-accord</link>
      <pubDate>Thu, 16 Aug 2026 09:30:00 +0000</pubDate>
      <description>&lt;p&gt;Global leaders sign international AI safety agreement.&lt;/p&gt;</description>
    </item>
  </channel>
</rss>"""

SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom AI Feed</title>
  <entry>
    <title>Atom AI Breakthrough</title>
    <link rel="alternate" href="https://example.com/atom-ai"/>
    <published>2026-08-15T10:00:00Z</published>
    <summary>Atom feed summary content about artificial intelligence.</summary>
  </entry>
</feed>"""


def test_parse_news_rss_feed():
    articles = parse_news_rss(SAMPLE_RSS_FEED)
    assert len(articles) == 2

    a1 = articles[0]
    assert a1.title == "Startup Launches Next-Gen AI Model"
    assert a1.url == "https://techcrunch.com/2026/08/15/ai-startup-model"
    assert a1.published_date.year == 2026
    assert a1.source_name == "TechCrunch AI"
    assert a1.full_text is not None
    assert "Startup XYZ has announced" in a1.full_text


def test_parse_news_atom_feed():
    articles = parse_news_rss(SAMPLE_ATOM_FEED)
    assert len(articles) == 1

    a1 = articles[0]
    assert a1.title == "Atom AI Breakthrough"
    assert a1.url == "https://example.com/atom-ai"
    assert a1.published_date.year == 2026
    assert a1.source_name == "Atom AI Feed"


def test_parse_pub_date_valid_rfc822():
    dt = parse_pub_date("Wed, 15 Aug 2026 12:00:00 +0000")
    assert dt.year == 2026
    assert dt.month == 8
    assert dt.day == 15


def test_parse_pub_date_invalid_fallback():
    dt = parse_pub_date("not-a-date")
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


def test_extract_clean_text():
    html = "<html><head><style>body {color:red;}</style></head><body><script>alert(1);</script><nav>Header</nav><p>Main article body text goes here.</p></body></html>"
    extracted = extract_clean_text(html)
    assert extracted is not None
    assert "Main article body text" in extracted
    assert "alert" not in extracted
    assert "color:red" not in extracted


def test_qualify_news_article():
    art_valid = RawNewsArticle(
        title="Valid Title",
        url="https://example.com/article",
        published_date=datetime.now(timezone.utc),
    )
    assert qualify_news_article(art_valid) is True

    art_empty_title = RawNewsArticle(
        title="",
        url="https://example.com/article",
        published_date=datetime.now(timezone.utc),
    )
    assert qualify_news_article(art_empty_title) is False

    art_invalid_url = RawNewsArticle(
        title="Title",
        url="ftp://invalid",
        published_date=datetime.now(timezone.utc),
    )
    assert qualify_news_article(art_invalid_url) is False


def test_news_pydantic_model_validation():
    now = datetime.now(timezone.utc)
    news = News(
        source={"name": "TechCrunch", "url": "https://techcrunch.com"},
        content={
            "title": "AI Breakthrough",
            "url": "https://techcrunch.com/2026/08/15/breakthrough",
            "published_date": now,
            "full_text": "Detailed text content",
        },
        collectedAt=now,
    )
    assert news.recordType == "NEWS"
    assert news.content.title == "AI Breakthrough"

    with pytest.raises(ValidationError):
        News(
            source={"name": "TechCrunch", "url": "https://techcrunch.com"},
            content={
                "title": "",  # Min length 1 violation
                "url": "https://techcrunch.com/test",
                "published_date": now,
            },
            collectedAt=now,
        )


def test_news_repository_save_and_duplicate():
    mock_col = MagicMock()
    mock_col.count_documents.side_effect = [0, 1, 1]  # 1st save check, explicit check, 2nd save check
    mock_col.insert_one = MagicMock()

    mock_db = {"news": mock_col}
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    repo = NewsRepository(client=mock_client)
    repo.setup_indexes()

    now = datetime.now(timezone.utc)
    news = News(
        source={"name": "TechCrunch", "url": "https://techcrunch.com"},
        content={
            "title": "Unique News Article",
            "url": "https://techcrunch.com/2026/08/15/unique-article",
            "published_date": now,
            "full_text": "Sample text",
        },
        collectedAt=now,
    )

    # 1. First save -> True
    saved_first = repo.save(news)
    assert saved_first is True

    # 2. Duplicate check -> exists True
    assert repo.exists("https://techcrunch.com/2026/08/15/unique-article") is True

    # 3. Second save -> False
    saved_second = repo.save(news)
    assert saved_second is False


@pytest.mark.asyncio
async def test_news_adapter_discovery():
    mock_client = AsyncMock()
    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=SAMPLE_RSS_FEED,
    )

    settings = MagicMock()
    settings.news_sources = "techcrunch"

    adapter = NewsAdapter(settings=settings, client=mock_client)
    articles = await adapter.discover_articles(limit=10)

    assert len(articles) == 2
    assert articles[0].title == "Startup Launches Next-Gen AI Model"
    await adapter.close()


@pytest.mark.asyncio
async def test_news_service_ingest():
    settings = MagicMock()
    settings.mongodb_uri = "mongodb://localhost:27017"
    settings.mongodb_database = "test_ai_intelligence_pipeline"
    settings.news_sources = "techcrunch"

    mock_client = AsyncMock()
    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=SAMPLE_RSS_FEED,
    )

    mock_mongo_col = MagicMock()
    # Run 1 find returns empty (no duplicates), insert_many returns 2 IDs
    # Run 2 find returns existing URLs (2 duplicates)
    mock_mongo_col.find.side_effect = [
        [],
        [
            {"content": {"url": "https://techcrunch.com/2026/08/15/ai-startup"}},
            {"content": {"url": "https://techcrunch.com/2026/08/15/open-source-llm"}},
        ],
    ]
    mock_mongo_col.count_documents.side_effect = [0, 0, 1, 1]
    mock_insert_res = MagicMock()
    mock_insert_res.inserted_ids = ["id1", "id2"]
    mock_mongo_col.insert_many.return_value = mock_insert_res
    mock_cp_col = MagicMock()
    mock_cp_col.find_one.return_value = None
    mock_mongo_db = {"news": mock_mongo_col, "checkpoints": mock_cp_col}
    mock_mongo_client = MagicMock()
    mock_mongo_client.__getitem__.return_value = mock_mongo_db

    with patch("src.crawlers.news.adapter.AsyncHttpClient.from_settings", return_value=mock_client), patch("src.storage.repositories.news.MongoClient", return_value=mock_mongo_client), patch("src.storage.checkpoints.MongoClient", return_value=mock_mongo_client):
        svc = NewsService(settings=settings)
        res1 = await svc.ingest(limit=10)

        assert res1["status"] == "success"
        assert res1["discovered"] == 2
        assert res1["inserted"] == 2
        assert res1["duplicates"] == 0

        # Second run -> duplicates only
        res2 = await svc.ingest(limit=10, resume=False)
        assert res2["status"] == "success"
        assert res2["inserted"] == 0
        assert res2["duplicates"] == 2

