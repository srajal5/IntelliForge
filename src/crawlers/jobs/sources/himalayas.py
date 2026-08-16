"""Himalayas Tech Jobs public API job source."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.crawlers.jobs.models import RawJobPosting
from src.crawlers.jobs.sources.base import BaseJobSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

HIMALAYAS_API_URL = "https://himalayas.app/jobs/api"


class HimalayasSource(BaseJobSource):
    """Discovers tech jobs from Himalayas public API."""

    source_key = "himalayas"
    source_name = "Himalayas Tech Jobs"
    source_url = "https://himalayas.app/jobs"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawJobPosting]:
        discovered: list[RawJobPosting] = []
        per_page = 50
        api_offset = offset

        url = f"{HIMALAYAS_API_URL}?limit={per_page}&offset={api_offset}"
        result = await self.client.fetch(url)

        if not result.success or not result.content:
            logger.warning("himalayas_fetch_failed", status=result.status_code)
            return discovered

        try:
            data = json.loads(result.content)
            jobs = data.get("jobs", [])
            if not isinstance(jobs, list):
                return discovered
        except Exception as json_err:
            logger.warning("himalayas_json_failed", error=str(json_err))
            return discovered

        for item in jobs:
            if len(discovered) >= limit:
                break

            job_title = item.get("title", "").strip()
            company_name = item.get("companyName", "").strip()
            canonical_url = item.get("applicationLink") or item.get("excerptUrl") or f"https://himalayas.app/jobs/{item.get('slug', '')}"
            pub_date_raw = item.get("pubDate")

            if not job_title or not company_name:
                continue

            posted_at = datetime.now(timezone.utc)
            if pub_date_raw:
                try:
                    posted_at = datetime.fromtimestamp(int(pub_date_raw), tz=timezone.utc)
                except Exception:
                    pass

            desc = item.get("excerpt") or item.get("description") or job_title

            raw_job = RawJobPosting(
                company=company_name,
                title=job_title,
                url=canonical_url,
                date=posted_at,
                is_remote=True,
                description=desc,
                source_name=self.source_name,
                source_url=self.source_url,
                is_qualified=True,
            )
            discovered.append(raw_job)

        return discovered
