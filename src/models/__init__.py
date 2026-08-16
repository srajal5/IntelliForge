"""Canonical data models for the AI Intelligence Pipeline.

All models enforce strict validation via Pydantic:
- URLs must be valid HTTP(S) URLs.
- Timestamps must be valid ISO-8601.
- Enums reject arbitrary values.
- Required fields cannot be omitted.
- Extra fields are forbidden.
"""

from src.models.enums import RecordType, PricingModel, MatchMethod
from src.models.base import CanonicalBase, Source
from src.models.startup import Startup, StartupContent, StartupData
from src.models.product import Product, ProductContent
from src.models.research_paper import ResearchPaper, ResearchPaperContent
from src.models.job import Job, JobContent
from src.models.news import News, NewsContent
from src.models.entity_mapping import EntityMapping

__all__ = [
    # Enums
    "RecordType",
    "PricingModel",
    "MatchMethod",
    # Base
    "CanonicalBase",
    "Source",
    # Models
    "Startup",
    "StartupContent",
    "StartupData",
    "Product",
    "ProductContent",
    "ResearchPaper",
    "ResearchPaperContent",
    "Job",
    "JobContent",
    "News",
    "NewsContent",
    "EntityMapping",
]
