"""Main Entity Resolver orchestrating normalizer, matcher, repository, and fallback."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.entity.blocking import filter_candidates_with_blocking
from src.entity.fallback_interface import EntityLLMFallbackInterface, MockEntityLLMFallback
from src.entity.matcher import EntityMatcher, MatchResult
from src.entity.models import CanonicalEntity
from src.entity.normalizer import normalize_entity_name
from src.entity.repository import EntityRepository
from src.models.entity_mapping import EntityMapping
from src.models.enums import MatchMethod
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EntityResolver:
    """Orchestrates multi-stage entity resolution and mapping persistence."""

    def __init__(
        self,
        repository: EntityRepository | None = None,
        llm_fallback: EntityLLMFallbackInterface | None = None,
    ) -> None:
        self.repository = repository or EntityRepository()
        self.llm_fallback = llm_fallback or MockEntityLLMFallback()
        self.matcher = EntityMatcher(llm_fallback=self.llm_fallback)
        self._memory_cache: dict[str, EntityMapping] = {}

    def resolve_entity(
        self,
        raw_name: str,
        source_url: str | None = None,
        entity_type: str = "STARTUP",
        source_context: dict[str, Any] | None = None,
    ) -> EntityMapping:
        """Resolve a raw entity name to a Canonical Entity and record the EntityMapping.

        Guarantees idempotency: if the raw_name has already been resolved, the existing mapping is returned.
        """
        raw_clean = (raw_name or "").strip()
        if not raw_clean:
            now = datetime.now(timezone.utc)
            return EntityMapping(
                raw_name="UNKNOWN",
                normalized_name="",
                canonical_name="UNKNOWN",
                canonical_id="unresolved_unknown",
                match_method=MatchMethod.UNRESOLVED,
                confidence=0.0,
                source_url=source_url,
                timestamp=now,
            )

        # 0. Fast In-Memory Cache Check
        if raw_clean in self._memory_cache:
            return self._memory_cache[raw_clean]

        # 1. Idempotency Check: Return existing mapping from repository if present
        existing = self.repository.get_mapping_by_raw_name(raw_clean)
        if existing:
            self._memory_cache[raw_clean] = existing
            logger.info("entity_resolution_cached", raw_name=raw_clean, canonical_id=existing.canonical_id)
            return existing

        # 2. Load candidate entities from repository & apply Candidate Blocking
        candidates = self.repository.get_all_canonical_entities()
        if len(candidates) > 10:
            candidates = filter_candidates_with_blocking(raw_clean, candidates)

        # 3. Execute multi-stage match pipeline safely
        try:
            match_res: MatchResult = self.matcher.match(
                raw_name=raw_clean,
                candidates=candidates,
                source_context=source_context,
            )
        except Exception as exc:
            logger.warning("entity_matcher_exception_fallback", raw_name=raw_clean, error=str(exc))
            match_res = MatchResult(
                canonical_id=None,
                canonical_name=None,
                match_method=MatchMethod.UNRESOLVED,
                confidence=0.0,
                candidates=[],
            )

        norm_name = normalize_entity_name(raw_clean)

        # 4. Handle Match Outcome
        if match_res.canonical_id and match_res.match_method != MatchMethod.UNRESOLVED:
            canonical_id = match_res.canonical_id
            canonical_name = match_res.canonical_name or raw_clean

            # Persist raw_name as alias if new
            self.repository.add_alias_to_canonical(canonical_id, raw_clean)

        else:
            # Unresolved record
            canonical_id = f"unresolved_{norm_name or 'entity'}"
            canonical_name = raw_clean
            match_res = MatchResult(
                canonical_id=canonical_id,
                canonical_name=canonical_name,
                match_method=MatchMethod.UNRESOLVED,
                confidence=0.0,
                candidates=match_res.candidates,
            )

        now = datetime.now(timezone.utc)
        mapping = EntityMapping(
            raw_name=raw_clean,
            normalized_name=norm_name or raw_clean.lower(),
            canonical_name=canonical_name,
            canonical_id=canonical_id,
            match_method=match_res.match_method,
            confidence=match_res.confidence,
            source_url=source_url,
            timestamp=now,
        )

        # 5. Persist EntityMapping into repository
        self.repository.save_entity_mapping(mapping)
        self._memory_cache[raw_clean] = mapping
        logger.info(
            "entity_resolved",
            raw_name=raw_clean,
            canonical_id=canonical_id,
            method=match_res.match_method.value,
            confidence=match_res.confidence,
        )
        return mapping
