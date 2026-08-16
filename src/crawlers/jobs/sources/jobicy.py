"""Jobicy Remote Jobs API source."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.crawlers.jobs.models import RawJobPosting
from src.crawlers.jobs.parser import parse_job_date
from src.crawlers.jobs.qualifier import qualify_job_posting
from src.crawlers.jobs.sources.base import BaseJobSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs?count=50"


class JobicySource(BaseJobSource):
    """Discovers remote tech jobs from Jobicy API."""

    source_key = "jobicy"
    source_name = "Jobicy Remote Jobs"
    source_url = "https://jobicy.com"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawJobPosting]:
        discovered: list[RawJobPosting] = []
        result = await self.client.fetch(JOBICY_API)

        if not result.success or not result.content:
            logger.warning("jobicy_fetch_failed", status=result.status_code)
            return discovered

        try:
            data = json.loads(result.content)
            jobs_data = data.get("jobs", [])
        except Exception as json_err:
            logger.warning("jobicy_json_failed", error=str(json_err))
            return discovered

        selected = jobs_data[offset:] if offset < len(jobs_data) else []

        for item in selected:
            if len(discovered) >= limit:
                break

            company = item.get("companyName", "").strip() or "Unknown Company"
            title = item.get("jobTitle", "").strip()
            url = item.get("url", "").strip()
            pub_date_s = item.get("pubDate")
            dt = parse_job_date(pub_date_s) if pub_date_s else datetime.now(timezone.utc)
            desc = item.get("jobDescription")

            if not title or not url:
                continue

            posting = RawJobPosting(
                company=company,
                title=title,
                url=url,
                date=dt,
                is_remote=True,
                description=desc,
                source_name=self.source_name,
                source_url=self.source_url,
            )

            if qualify_job_posting(posting):
                discovered.append(posting)

        return discovered
