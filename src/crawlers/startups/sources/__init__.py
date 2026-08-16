"""Modular startup sources package."""

from __future__ import annotations

from typing import Type

from src.crawlers.client import AsyncHttpClient
from src.crawlers.startups.sources.base import BaseStartupSource
from src.crawlers.startups.sources.github_orgs import GitHubOrgsSource

STARTUP_SOURCE_REGISTRY: dict[str, Type[BaseStartupSource]] = {
    "github_orgs": GitHubOrgsSource,
}


def get_startup_sources(
    enabled_keys: str | list[str], client: AsyncHttpClient
) -> list[BaseStartupSource]:
    """Instantiate enabled Startup sources based on config key list."""
    if isinstance(enabled_keys, str):
        keys = [k.strip().lower() for k in enabled_keys.split(",") if k.strip()]
    else:
        keys = [k.strip().lower() for k in enabled_keys if k.strip()]

    sources: list[BaseStartupSource] = []
    for key in keys:
        source_cls = STARTUP_SOURCE_REGISTRY.get(key)
        if source_cls:
            sources.append(source_cls(client))

    if not sources:
        sources.append(GitHubOrgsSource(client))

    return sources
