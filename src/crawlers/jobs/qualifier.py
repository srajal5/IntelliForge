"""Job posting quality validation logic."""

from __future__ import annotations

from src.crawlers.jobs.models import RawJobPosting


def qualify_job_posting(job: RawJobPosting) -> bool:
    """Validate that a job posting record has required minimum fields."""
    if not job.company or not job.company.strip():
        return False
    if not job.title or not job.title.strip():
        return False
    if not job.url or not job.url.strip() or not job.url.startswith("http"):
        return False
    return True
