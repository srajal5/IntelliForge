"""Modular job sources package."""

from __future__ import annotations

from typing import Type

from src.crawlers.client import AsyncHttpClient
from src.crawlers.jobs.sources.arbeitnow import ArbeitnowSource
from src.crawlers.jobs.sources.base import BaseJobSource
from src.crawlers.jobs.sources.himalayas import HimalayasSource
from src.crawlers.jobs.sources.jobicy import JobicySource
from src.crawlers.jobs.sources.remoteok import RemoteOKSource
from src.crawlers.jobs.sources.weworkremotely import WeWorkRemotelySource

JOB_SOURCE_REGISTRY: dict[str, Type[BaseJobSource]] = {
    "arbeitnow": ArbeitnowSource,
    "remoteok": RemoteOKSource,
    "jobicy": JobicySource,
    "weworkremotely": WeWorkRemotelySource,
    "himalayas": HimalayasSource,
}


def get_job_sources(
    enabled_keys: str | list[str], client: AsyncHttpClient
) -> list[BaseJobSource]:
    """Instantiate enabled Job sources based on config key list."""
    if isinstance(enabled_keys, str):
        keys = [k.strip().lower() for k in enabled_keys.split(",") if k.strip()]
    else:
        keys = [k.strip().lower() for k in enabled_keys if k.strip()]

    sources: list[BaseJobSource] = []
    for key in keys:
        source_cls = JOB_SOURCE_REGISTRY.get(key)
        if source_cls:
            sources.append(source_cls(client))

    # Fallback if no valid key matched
    if not sources:
        sources.append(ArbeitnowSource(client))

    return sources
