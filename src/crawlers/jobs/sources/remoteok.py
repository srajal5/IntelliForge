"""RemoteOK API job source."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.crawlers.jobs.models import RawJobPosting
from src.crawlers.jobs.parser import parse_job_date
from src.crawlers.jobs.qualifier import qualify_job_posting
from src.crawlers.jobs.sources.base import BaseJobSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

REMOTEOK_API = "https://remoteok.com/api"


class RemoteOKSource(BaseJobSource):
    """Discovers tech jobs from RemoteOK API."""

    source_key = "remoteok"
    source_name = "RemoteOK Jobs"
    source_url = "https://remoteok.com"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawJobPosting]:
        discovered: list[RawJobPosting] = []
        result = await self.client.fetch(REMOTEOK_API)

        if not result.success or not result.content:
            logger.warning("remoteok_fetch_failed", status=result.status_code)
            return discovered

        try:
            data = json.loads(result.content)
            if isinstance(data, list):
                # First element in RemoteOK JSON response is legal notice object
                jobs_data = [j for j in data if isinstance(j, dict) and "position" in j]
            else:
                jobs_data = []
        except Exception as json_err:
            logger.warning("remoteok_json_failed", error=str(json_err))
            return discovered

        selected = jobs_data[offset:] if offset < len(jobs_data) else []

        for item in selected:
            if len(discovered) >= limit:
                break

            company = item.get("company", "").strip() or "Unknown Company"
            title = item.get("position", "").strip()
            url = item.get("url") or item.get("apply_url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
            date_val = item.get("date")
            dt = parse_job_date(str(date_val)) if date_val else datetime.now(timezone.utc)
            desc = item.get("description")

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
