"""Tests for ArXiv Atom XML feed parsing."""

from datetime import datetime, timezone
import pytest

from src.crawlers.research.parser import ArxivParser

SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2103.14030v1</id>
    <published>2021-03-25T17:59:00Z</published>
    <title>
      Swin Transformer: Hierarchical Vision Transformer using Shifted Windows
    </title>
    <summary>
      This paper presents a new Vision Transformer, called Swin Transformer...
      Code at https://github.com/microsoft/Swin-Transformer
    </summary>
    <author>
      <name>Ze Liu</name>
    </author>
    <author>
      <name>Yutong Lin</name>
    </author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/1706.03762v5</id>
    <published>2017-06-12T00:00:00Z</published>
    <title>Attention Is All You Need</title>
    <summary>The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...</summary>
    <author>
      <name>Ashish Vaswani</name>
    </author>
  </entry>
</feed>
"""


def test_parse_valid_feed():
    papers = ArxivParser.parse_feed(SAMPLE_ATOM_XML)
    assert len(papers) == 2

    p1 = papers[0]
    assert p1.title == "Swin Transformer: Hierarchical Vision Transformer using Shifted Windows"
    assert p1.authors == ["Ze Liu", "Yutong Lin"]
    assert p1.paper_url == "https://arxiv.org/abs/2103.14030"
    assert "Swin Transformer" in p1.summary
    assert p1.published_date == datetime(2021, 3, 25, 17, 59, tzinfo=timezone.utc)
    assert p1.source_name == "arXiv"

    p2 = papers[1]
    assert p2.title == "Attention Is All You Need"
    assert p2.authors == ["Ashish Vaswani"]
    assert p2.paper_url == "https://arxiv.org/abs/1706.03762"


def test_parse_empty_feed():
    papers = ArxivParser.parse_feed("")
    assert papers == []


def test_parse_malformed_xml():
    papers = ArxivParser.parse_feed("<feed><entry>broken xml")
    assert papers == []


def test_normalize_arxiv_url():
    assert ArxivParser._normalize_arxiv_url("http://arxiv.org/abs/2103.14030v1") == "https://arxiv.org/abs/2103.14030"
    assert ArxivParser._normalize_arxiv_url("https://arxiv.org/abs/2103.14030") == "https://arxiv.org/abs/2103.14030"
    assert ArxivParser._normalize_arxiv_url("2103.14030") == "https://arxiv.org/abs/2103.14030"
    assert ArxivParser._normalize_arxiv_url("") == ""


def test_date_parsing():
    dt = ArxivParser._parse_date("2024-03-15T12:30:00Z")
    assert dt == datetime(2024, 3, 15, 12, 30, tzinfo=timezone.utc)

    invalid_dt = ArxivParser._parse_date("not-a-date")
    assert invalid_dt is None
