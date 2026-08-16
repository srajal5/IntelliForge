"""Unit tests for modular job source adapters."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.crawlers.jobs.sources.jobicy import JobicySource
from src.crawlers.jobs.sources.remoteok import RemoteOKSource
from src.crawlers.jobs.sources.weworkremotely import WeWorkRemotelySource


@pytest.mark.asyncio
async def test_remoteok_source():
    mock_client = AsyncMock()
    remoteok_payload = [
        {"legal": "notice"},
        {
            "id": "1001",
            "company": "DeepMind AI Labs",
            "position": "Senior AI Infrastructure Engineer",
            "url": "https://remoteok.com/remote-jobs/1001",
            "date": 1786876800,
            "description": "Building next-gen AI infrastructure.",
        },
    ]
    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=json.dumps(remoteok_payload),
    )

    source = RemoteOKSource(client=mock_client)
    postings = await source.discover(limit=5, offset=0)

    assert len(postings) == 1
    assert postings[0].company == "DeepMind AI Labs"
    assert postings[0].title == "Senior AI Infrastructure Engineer"
    assert postings[0].source_name == "RemoteOK Jobs"


@pytest.mark.asyncio
async def test_jobicy_source():
    mock_client = AsyncMock()
    jobicy_payload = {
        "jobs": [
            {
                "companyName": "Anthropic Research",
                "jobTitle": "Lead Machine Learning Scientist",
                "url": "https://jobicy.com/jobs/lead-ml-scientist",
                "pubDate": "2026-08-16 10:00:00",
                "jobDescription": "LLM alignment and research.",
            }
        ]
    }
    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=json.dumps(jobicy_payload),
    )

    source = JobicySource(client=mock_client)
    postings = await source.discover(limit=5, offset=0)

    assert len(postings) == 1
    assert postings[0].company == "Anthropic Research"
    assert postings[0].title == "Lead Machine Learning Scientist"
    assert postings[0].source_name == "Jobicy Remote Jobs"


@pytest.mark.asyncio
async def test_weworkremotely_source():
    mock_client = AsyncMock()
    rss_data = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>We Work Remotely</title>
        <link>https://weworkremotely.com</link>
        <item>
          <title>OpenAI: Principal Systems Architect</title>
          <link>https://weworkremotely.com/jobs/openai-principal-architect</link>
          <pubDate>Sun, 16 Aug 2026 09:00:00 +0000</pubDate>
          <description>Lead large-scale compute infrastructure.</description>
        </item>
      </channel>
    </rss>"""

    mock_client.fetch.return_value = MagicMock(
        is_success=True,
        status_code=200,
        content=rss_data,
    )

    source = WeWorkRemotelySource(client=mock_client)
    postings = await source.discover(limit=5, offset=0)

    assert len(postings) == 1
    assert postings[0].company == "OpenAI"
    assert postings[0].title == "Principal Systems Architect"
    assert postings[0].source_name == "We Work Remotely"


@pytest.mark.asyncio
async def test_himalayas_source():
    from src.crawlers.jobs.sources.himalayas import HimalayasSource

    mock_client = AsyncMock()
    himalayas_payload = {
        "jobs": [
            {
                "id": "h-101",
                "title": "Senior AI Systems Engineer",
                "companyName": "NVIDIA",
                "applicationLink": "https://himalayas.app/jobs/nvidia-senior-ai-systems-engineer",
                "pubDate": 1786876800,
                "excerpt": "Architecting high performance AI cluster hardware.",
            }
        ]
    }
    mock_client.fetch.return_value = MagicMock(
        success=True,
        status_code=200,
        content=json.dumps(himalayas_payload),
    )

    source = HimalayasSource(client=mock_client)
    postings = await source.discover(limit=5, offset=0)

    assert len(postings) == 1
    assert postings[0].company == "NVIDIA"
    assert postings[0].title == "Senior AI Systems Engineer"
    assert postings[0].source_name == "Himalayas Tech Jobs"
