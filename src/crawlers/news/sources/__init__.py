"""Modular news sources package."""

from __future__ import annotations

from typing import Type

from src.crawlers.client import AsyncHttpClient
from src.crawlers.news.sources.arxiv_news import ArXivNewsSource
from src.crawlers.news.sources.base import BaseNewsSource
from src.crawlers.news.sources.devto import DEVtoAISource
from src.crawlers.news.sources.hackernews import HackerNewsSource
from src.crawlers.news.sources.huggingface import HuggingFaceSource
from src.crawlers.news.sources.kdnuggets import KDnuggetsSource
from src.crawlers.news.sources.mit_tech_review import MITTechReviewSource
from src.crawlers.news.sources.techcrunch import TechCrunchSource
from src.crawlers.news.sources.venturebeat import VentureBeatSource

NEWS_SOURCE_REGISTRY: dict[str, Type[BaseNewsSource]] = {
    "techcrunch": TechCrunchSource,
    "venturebeat": VentureBeatSource,
    "mit_tech_review": MITTechReviewSource,
    "hackernews": HackerNewsSource,
    "kdnuggets": KDnuggetsSource,
    "devto": DEVtoAISource,
    "huggingface": HuggingFaceSource,
    "arxiv": ArXivNewsSource,
}


def get_news_sources(
    enabled_keys: str | list[str], client: AsyncHttpClient
) -> list[BaseNewsSource]:
    """Instantiate enabled News sources based on config key list."""
    if isinstance(enabled_keys, str):
        keys = [k.strip().lower() for k in enabled_keys.split(",") if k.strip()]
    else:
        keys = [k.strip().lower() for k in enabled_keys if k.strip()]

    sources: list[BaseNewsSource] = []
    for key in keys:
        source_cls = NEWS_SOURCE_REGISTRY.get(key)
        if source_cls:
            sources.append(source_cls(client))

    # Fallback if no valid key matched
    if not sources:
        sources.append(TechCrunchSource(client))

    return sources
