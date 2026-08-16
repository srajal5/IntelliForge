"""Parser for Job postings JSON/RSS payloads, remote status, and role family classification."""

from __future__ import annotations

from datetime import datetime, timezone
import email.utils
import json
import re
from typing import Any

from src.crawlers.jobs.models import RawJobPosting
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Deterministic role family keyword mappings
ROLE_FAMILY_KEYWORDS: dict[str, list[str]] = {
    "Engineering": [
        "software engineer",
        "software developer",
        "backend",
        "frontend",
        "full stack",
        "fullstack",
        "architect",
        "programmer",
        "web developer",
        "python developer",
        "golang engineer",
        "java engineer",
        "c++ developer",
        "ios developer",
        "android engineer",
    ],
    "Data & AI": [
        "machine learning",
        "ml engineer",
        "data scientist",
        "ai engineer",
        "artificial intelligence",
        "deep learning",
        "nlp",
        "computer vision",
        "data engineer",
        "mlops",
        "data analyst",
        "research scientist",
    ],
    "Infrastructure": [
        "devops",
        "site reliability",
        "sre",
        "cloud engineer",
        "infrastructure",
        "sysadmin",
        "system administrator",
        "platform engineer",
        "kubernetes",
    ],
    "Security": [
        "security engineer",
        "cybersecurity",
        "infosec",
        "penetration tester",
        "security analyst",
    ],
    "Quality Assurance": [
        "qa engineer",
        "quality assurance",
        "test engineer",
        "sdet",
        "qa",
    ],
    "Product & Design": [
        "product manager",
        "project manager",
        "scrum master",
        "ui/ux",
        "product designer",
        "ux designer",
    ],
}


def parse_job_date(val: Any) -> datetime:
    """Parse posting date timestamp, ISO string, or RFC 822 date into UTC datetime."""
    if val is None:
        return datetime.now(timezone.utc)

    # If already a datetime
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val

    # Unix timestamp (int/float)
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except Exception:
            pass

    # String timestamp
    val_str = str(val).strip()
    if not val_str:
        return datetime.now(timezone.utc)

    # String containing digits only (Unix timestamp)
    if val_str.isdigit():
        try:
            return datetime.fromtimestamp(int(val_str), tz=timezone.utc)
        except Exception:
            pass

    # Try ISO 8601
    try:
        iso_str = val_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    # Try RFC 822
    try:
        dt = email.utils.parsedate_to_datetime(val_str)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass

    return datetime.now(timezone.utc)


def detect_remote_status(raw_data: dict[str, Any], title: str, description: str | None = None) -> bool:
    """Detect if job posting is remote based on explicit indicators or text keywords."""
    # 1. Direct boolean flag
    if "remote" in raw_data and isinstance(raw_data["remote"], bool):
        return raw_data["remote"]

    # 2. Direct string flag
    remote_flag = str(raw_data.get("remote", "")).lower()
    if remote_flag in ("true", "1", "yes"):
        return True
    if remote_flag in ("false", "0", "no", "onsite"):
        return False

    # 3. Check location string
    location = str(raw_data.get("location", "")).lower()
    if "remote" in location or "anywhere" in location or "work from home" in location or "wfh" in location:
        return True

    # 4. Check title and description
    combined = f"{title} {description or ''}".lower()
    if "onsite only" in combined or "in-office only" in combined or "relocation required" in combined:
        return False

    if any(kw in combined for kw in ["remote", "work from anywhere", "work from home", "wfh", "telecommute"]):
        return True

    return False


def classify_role_family_deterministic(title: str, description: str | None = None) -> str | None:
    """Classify job title into a canonical role family deterministically."""
    text = f"{title} {description or ''}".lower()

    for role_family, keywords in ROLE_FAMILY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return role_family

    return None


async def classify_role_family(
    title: str,
    description: str | None = None,
    orchestrator: Any | None = None,
) -> str | None:
    """Classify role family deterministically first, falling back to LLM if ambiguous and permitted."""
    # 1. Deterministic classification
    determined = classify_role_family_deterministic(title, description)
    if determined:
        return determined

    # 2. LLM fallback if orchestrator is available
    if orchestrator is None:
        return None

    try:
        prompt = (
            f"Classify the following job title into exactly one of these role families: "
            f"['Engineering', 'Data & AI', 'Infrastructure', 'Security', 'Quality Assurance', 'Product & Design'].\n"
            f"Job Title: {title}\n"
            f"Return ONLY the exact role family name as plain text."
        )
        response = await orchestrator.generate(prompt=prompt, system_prompt="You are a job classification system.")
        if response and response.success and response.text:
            cleaned = response.text.strip().strip('"').strip("'")
            valid_families = {
                "Engineering",
                "Data & AI",
                "Infrastructure",
                "Security",
                "Quality Assurance",
                "Product & Design",
            }
            if cleaned in valid_families:
                return cleaned
    except Exception as exc:
        logger.debug("llm_role_family_classification_failed", error=str(exc))

    return None


def parse_job_item(item: dict[str, Any], source_name: str = "Arbeitnow Tech Jobs") -> RawJobPosting | None:
    """Parse raw dictionary item from job API into RawJobPosting model."""
    if not isinstance(item, dict):
        return None

    company = item.get("company_name") or item.get("company") or item.get("company_title") or ""
    title = item.get("title") or item.get("position") or item.get("role") or ""
    url = item.get("url") or item.get("link") or item.get("job_url") or ""

    company = str(company).strip()
    title = str(title).strip()
    url = str(url).strip()

    if not company or not title or not url:
        return None

    date_raw = item.get("created_at") or item.get("date") or item.get("posted_at") or item.get("published_at")
    posting_date = parse_job_date(date_raw)

    description = item.get("description") or item.get("text") or ""
    if description:
        # Strip HTML tags if present in description
        description = re.sub(r"<[^>]+>", " ", str(description))
        description = re.sub(r"\s+", " ", description).strip()

    is_remote = detect_remote_status(item, title, description)
    role_family = classify_role_family_deterministic(title, description)

    return RawJobPosting(
        company=company,
        title=title,
        url=url,
        date=posting_date,
        is_remote=is_remote,
        description=description if description else None,
        role_family=role_family,
        source_name=source_name,
        source_url="https://www.arbeitnow.com/api/job-board-api",
    )
