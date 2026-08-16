"""Modular product sources package."""

from __future__ import annotations

from typing import Type

from src.crawlers.client import AsyncHttpClient
from src.crawlers.products.sources.base import BaseProductSource
from src.crawlers.products.sources.github_repos import GitHubReposSource

PRODUCT_SOURCE_REGISTRY: dict[str, Type[BaseProductSource]] = {
    "github_repos": GitHubReposSource,
}


def get_product_sources(
    enabled_keys: str | list[str], client: AsyncHttpClient
) -> list[BaseProductSource]:
    """Instantiate enabled Product sources based on config key list."""
    if isinstance(enabled_keys, str):
        keys = [k.strip().lower() for k in enabled_keys.split(",") if k.strip()]
    else:
        keys = [k.strip().lower() for k in enabled_keys if k.strip()]

    sources: list[BaseProductSource] = []
    for key in keys:
        source_cls = PRODUCT_SOURCE_REGISTRY.get(key)
        if source_cls:
            sources.append(source_cls(client))

    if not sources:
        sources.append(GitHubReposSource(client))

    return sources
