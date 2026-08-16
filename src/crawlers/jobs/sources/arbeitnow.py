"""Arbeitnow Tech Jobs API source."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.crawlers.jobs.models import RawJobPosting
from src.crawlers.jobs.parser import parse_job_date, parse_job_item
from src.crawlers.jobs.qualifier import qualify_job_posting
from src.crawlers.jobs.sources.base import BaseJobSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource(BaseJobSource):
    """Discovers tech jobs from Arbeitnow API."""

    source_key = "arbeitnow"
    source_name = "Arbeitnow Tech Jobs"
    source_url = ARBEITNOW_API

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawJobPosting]:
        discovered: list[RawJobPosting] = []
        page = (offset // 15) + 1
        item_offset = offset % 15

        url = f"{ARBEITNOW_API}?page={page}"
        result = await self.client.fetch(url)

        if not result.success or not result.content:
            logger.warning("arbeitnow_fetch_failed", status=result.status_code, page=page)
            return discovered

        try:
            data = json.loads(result.content)
            jobs_data = data.get("data", [])
        except Exception as json_err:
            logger.warning("arbeitnow_json_failed", error=str(json_err))
            return discovered

        selected = jobs_data[item_offset:] if item_offset < len(jobs_data) else jobs_data

        for raw_job in selected:
            if len(discovered) >= limit:
                break

            parsed = parse_job_item(raw_job, source_name=self.source_name)
            if parsed and qualify_job_posting(parsed):
                discovered.append(parsed)

        return discovered
