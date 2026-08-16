"""We Work Remotely RSS job source."""

from __future__ import annotations

import email.utils
from datetime import datetime, timezone
from defusedxml import ElementTree as ET

from src.crawlers.jobs.models import RawJobPosting
from src.crawlers.jobs.parser import parse_job_date
from src.crawlers.jobs.qualifier import qualify_job_posting
from src.crawlers.jobs.sources.base import BaseJobSource
from src.utils.logging import get_logger

logger = get_logger(__name__)

WWR_RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"


class WeWorkRemotelySource(BaseJobSource):
    """Discovers programming and tech jobs from We Work Remotely RSS feed."""

    source_key = "weworkremotely"
    source_name = "We Work Remotely"
    source_url = "https://weworkremotely.com"

    async def discover(self, limit: int = 10, offset: int = 0) -> list[RawJobPosting]:
        discovered: list[RawJobPosting] = []
        result = await self.client.fetch(WWR_RSS_URL)

        if not result.success or not result.content:
            logger.warning("weworkremotely_fetch_failed", status=result.status_code)
            return discovered

        try:
            root = ET.fromstring(result.content)
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []
        except Exception as xml_err:
            logger.warning("weworkremotely_xml_failed", error=str(xml_err))
            return discovered

        selected = items[offset:] if offset < len(items) else []

        for item in selected:
            if len(discovered) >= limit:
                break

            title_elem = item.find("title")
            link_elem = item.find("link")
            pub_elem = item.find("pubDate")
            desc_elem = item.find("description")

            raw_title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            pub_date_s = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

            if not raw_title or not url:
                continue

            # WWR titles format: "Company Name: Job Title"
            company = "We Work Remotely Company"
            job_title = raw_title
            if ":" in raw_title:
                parts = raw_title.split(":", 1)
                company = parts[0].strip()
                job_title = parts[1].strip()

            dt = parse_job_date(pub_date_s) if pub_date_s else datetime.now(timezone.utc)
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else None

            posting = RawJobPosting(
                company=company,
                title=job_title,
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
