"""Entity resolution and deduplication package."""

from src.entity.fallback_interface import (
    EntityLLMFallbackInterface,
    LLMFallbackCandidate,
    LLMFallbackResult,
    MockEntityLLMFallback,
)
from src.entity.matcher import EntityMatcher, MatchResult
from src.entity.models import CanonicalEntity
from src.entity.normalizer import normalize_entity_name
from src.entity.repository import EntityRepository
from src.entity.resolver import EntityResolver

__all__ = [
    "CanonicalEntity",
    "EntityRepository",
    "EntityMatcher",
    "EntityResolver",
    "MatchResult",
    "normalize_entity_name",
    "EntityLLMFallbackInterface",
    "LLMFallbackCandidate",
    "LLMFallbackResult",
    "MockEntityLLMFallback",
]
