"""Deterministic transformation layer for MongoDB documents to Google Sheets rows.

Transforms raw documents or canonical domain model dicts into validated,
header-aligned list of row values ready for batch insertion into Google Sheets.
"""

from __future__ import annotations

from typing import Any
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Column Definitions
RESEARCH_PAPERS_HEADERS = [
    "paper_url",
    "title",
    "authors",
    "published_date",
    "github_url",
    "github_stars",
    "abstract",
    "source_name",
    "source_url",
    "collected_at",
    "canonical_entity_id",
]

STARTUPS_HEADERS = [
    "entity_name",
    "website",
    "description",
    "employee_count",
    "founded_date",
    "location",
    "funding",
    "source_url",
    "category",
    "qualification_status",
    "canonical_entity_id",
    "collected_at",
]

PRODUCTS_HEADERS = [
    "product_name",
    "startup_name",
    "website",
    "description",
    "pricing_model",
    "source_url",
    "license",
    "qualification_category",
    "canonical_entity_id",
    "collected_at",
]

NEWS_HEADERS = [
    "title",
    "url",
    "published_date",
    "full_text",
    "source_name",
    "source_url",
    "canonical_entity_id",
    "collected_at",
]

JOBS_HEADERS = [
    "company",
    "date",
    "is_remote",
    "role_family",
    "url",
    "source_name",
    "canonical_entity_id",
    "collected_at",
]


def transform_research_paper(doc: dict[str, Any]) -> list[Any] | None:
    """Transform a ResearchPaper document into a sheet row.

    Returns None if essential fields are missing or invalid.
    """
    content = doc.get("content", {})
    title = content.get("title") or doc.get("title") or ""
    paper_url = content.get("paper_url") or doc.get("paper_url") or doc.get("source_url") or ""

    if not title or not paper_url:
        return None

    authors_raw = content.get("authors") or doc.get("authors") or []
    if isinstance(authors_raw, list):
        authors = ", ".join(str(a) for a in authors_raw)
    else:
        authors = str(authors_raw)

    published_date = str(content.get("published_date") or doc.get("published_date") or "")
    github_url = str(content.get("github_url") or doc.get("github_url") or "")
    github_stars = content.get("github_stars") if content.get("github_stars") is not None else doc.get("github_stars", "")
    if github_stars is None:
        github_stars = ""

    abstract = str(content.get("abstract") or doc.get("abstract") or "")
    source_name = doc.get("source", {}).get("name") or doc.get("source_name") or "arXiv/GitHub"
    source_url = doc.get("source", {}).get("url") or doc.get("source_url") or str(paper_url)
    collected_at = str(doc.get("collectedAt") or doc.get("collected_at") or "")
    canonical_entity_id = str(doc.get("canonical_entity_id") or "")

    return [
        str(paper_url),
        str(title),
        authors,
        published_date,
        github_url,
        github_stars,
        abstract,
        str(source_name),
        str(source_url),
        collected_at,
        canonical_entity_id,
    ]


def transform_startup(doc: dict[str, Any]) -> list[Any] | None:
    """Transform a Startup document into a sheet row.

    Rule: Only export values that actually exist in MongoDB.
    Do NOT infer employee count, funding, founded date, location.
    """
    content = doc.get("content", {})
    entity_name = content.get("entityName") or doc.get("canonical_name") or doc.get("entity_name") or ""
    if not entity_name:
        return None

    source_url = doc.get("source", {}).get("url") or doc.get("source_url") or ""
    website = doc.get("website") or source_url or ""
    description = doc.get("description") or content.get("description") or ""

    # Do not infer missing values
    data_dict = content.get("data", {})
    employee_count = data_dict.get("employeeCount") if isinstance(data_dict, dict) else None
    if employee_count is None:
        employee_count = doc.get("employee_count", "")

    founded_date = doc.get("founded_date") or (data_dict.get("foundedDate") if isinstance(data_dict, dict) else "") or ""
    location = doc.get("location") or (data_dict.get("location") if isinstance(data_dict, dict) else "") or ""
    funding = doc.get("funding") or (data_dict.get("funding") if isinstance(data_dict, dict) else "") or ""

    prov = doc.get("provenance", {})
    category = prov.get("category") or doc.get("category") or ""
    is_qualified = prov.get("is_qualified")
    if is_qualified is True:
        qualification_status = "QUALIFIED"
    elif is_qualified is False:
        qualification_status = "UNQUALIFIED"
    else:
        qualification_status = doc.get("qualification_status", "")

    canonical_entity_id = str(doc.get("canonical_entity_id") or "")
    collected_at = str(doc.get("collectedAt") or doc.get("collected_at") or "")

    return [
        str(entity_name),
        str(website),
        str(description),
        employee_count if employee_count is not None else "",
        str(founded_date),
        str(location),
        str(funding),
        str(source_url),
        str(category),
        str(qualification_status),
        canonical_entity_id,
        collected_at,
    ]


def transform_product(doc: dict[str, Any]) -> list[Any] | None:
    """Transform a Product document into a sheet row.

    Rule: license != pricing model. Do NOT infer pricing from license.
    """
    content = doc.get("content", {})
    prov = doc.get("provenance", {})

    product_name = (
        prov.get("product_name")
        or content.get("startupName")
        or doc.get("canonical_startup_name")
        or doc.get("product_name")
        or ""
    )
    if not product_name:
        return None

    startup_name = content.get("startupName") or doc.get("canonical_startup_name") or ""
    source_url = doc.get("source", {}).get("url") or doc.get("source_url") or ""
    website = doc.get("website") or source_url or ""
    description = doc.get("description") or prov.get("description") or ""

    pricing_model = content.get("pricingModel") or doc.get("pricing_model") or ""

    license_val = prov.get("license") or doc.get("license") or ""
    qualification_category = prov.get("category") or doc.get("category") or ""
    canonical_entity_id = str(doc.get("canonical_startup_id") or doc.get("canonical_entity_id") or "")
    collected_at = str(doc.get("collectedAt") or doc.get("collected_at") or "")

    return [
        str(product_name),
        str(startup_name),
        str(website),
        str(description),
        str(pricing_model) if pricing_model else "",
        str(source_url),
        str(license_val),
        str(qualification_category),
        canonical_entity_id,
        collected_at,
    ]


def transform_news(doc: dict[str, Any]) -> list[Any] | None:
    """Transform a News document into a sheet row.

    Rule: Do not modify article text during export.
    """
    content = doc.get("content", {})
    title = content.get("title") or doc.get("title") or ""
    url = content.get("url") or doc.get("url") or doc.get("source_url") or ""

    if not title or not url:
        return None

    published_date = str(content.get("published_date") or doc.get("published_date") or "")
    full_text = content.get("full_text") or doc.get("full_text") or ""

    prov = doc.get("provenance", {})
    source_name = doc.get("source", {}).get("name") or prov.get("source_name") or doc.get("source_name") or ""
    source_url = doc.get("source", {}).get("url") or doc.get("source_url") or str(url)
    canonical_entity_id = str(doc.get("canonical_entity_id") or "")
    collected_at = str(doc.get("collectedAt") or doc.get("collected_at") or "")

    return [
        str(title),
        str(url),
        published_date,
        str(full_text),
        str(source_name),
        str(source_url),
        canonical_entity_id,
        collected_at,
    ]


def transform_job(doc: dict[str, Any]) -> list[Any] | None:
    """Transform a Job document into a sheet row.

    Rule: Do not fabricate missing values.
    """
    content = doc.get("content", {})
    company = content.get("company") or doc.get("company") or ""
    date_val = str(content.get("date") or doc.get("date") or "")

    if not company:
        return None

    is_remote = content.get("is_remote")
    if is_remote is None:
        is_remote = doc.get("is_remote", "")

    role_family = content.get("role_family") or doc.get("role_family") or ""

    source_url = doc.get("source_url") or doc.get("source", {}).get("url") or ""
    prov = doc.get("provenance", {})
    source_name = doc.get("source", {}).get("name") or prov.get("source_name") or doc.get("source_name") or ""
    canonical_entity_id = str(doc.get("canonical_entity_id") or "")
    collected_at = str(doc.get("collectedAt") or doc.get("collected_at") or "")

    return [
        str(company),
        date_val,
        str(is_remote) if is_remote != "" else "",
        str(role_family),
        str(source_url),
        str(source_name),
        canonical_entity_id,
        collected_at,
    ]


VERTICAL_TRANSFORMERS = {
    "research": ("Research Papers", RESEARCH_PAPERS_HEADERS, transform_research_paper),
    "startups": ("Startups", STARTUPS_HEADERS, transform_startup),
    "products": ("Products", PRODUCTS_HEADERS, transform_product),
    "news": ("News", NEWS_HEADERS, transform_news),
    "jobs": ("Jobs", JOBS_HEADERS, transform_job),
}
