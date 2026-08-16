"""Matcher module executing the multi-stage Entity Resolution pipeline."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import NamedTuple

from src.entity.fallback_interface import (
    EntityLLMFallbackInterface,
    LLMFallbackCandidate,
)
from src.entity.models import CanonicalEntity
from src.entity.normalizer import normalize_entity_name
from src.models.enums import MatchMethod


class MatchResult(NamedTuple):
    """Result of matching a raw entity name against canonical candidates."""

    canonical_id: str | None
    canonical_name: str | None
    match_method: MatchMethod
    confidence: float
    candidates: list[LLMFallbackCandidate]


class EntityMatcher:
    """Multi-stage matcher: Exact -> Normalized -> Alias -> Fuzzy -> Ambiguity Check -> LLM Fallback."""

    def __init__(
        self,
        fuzzy_strong_threshold: float = 0.95,
        fuzzy_ambiguous_threshold: float = 0.80,
        ambiguity_delta: float = 0.03,
        llm_fallback: EntityLLMFallbackInterface | None = None,
    ):
        self.fuzzy_strong_threshold = fuzzy_strong_threshold
        self.fuzzy_ambiguous_threshold = fuzzy_ambiguous_threshold
        self.ambiguity_delta = ambiguity_delta
        self.llm_fallback = llm_fallback

    def match(
        self,
        raw_name: str,
        candidates: list[CanonicalEntity],
        source_context: dict | None = None,
    ) -> MatchResult:
        """Run the multi-stage match pipeline for a raw entity name."""
        if not raw_name or not candidates:
            return MatchResult(
                canonical_id=None,
                canonical_name=None,
                match_method=MatchMethod.UNRESOLVED,
                confidence=0.0,
                candidates=[],
            )

        raw_trimmed = raw_name.strip()
        norm_raw = normalize_entity_name(raw_name)

        # -------------------------------------------------------------
        # Stage 1: Exact Match
        # -------------------------------------------------------------
        for entity in candidates:
            if raw_trimmed == entity.canonical_name:
                return MatchResult(
                    canonical_id=entity.canonical_id,
                    canonical_name=entity.canonical_name,
                    match_method=MatchMethod.EXACT,
                    confidence=1.0,
                    candidates=[],
                )

        # -------------------------------------------------------------
        # Stage 2: Alias Match (exact string match in aliases)
        # -------------------------------------------------------------
        for entity in candidates:
            for alias in entity.aliases:
                if raw_trimmed == alias.strip():
                    return MatchResult(
                        canonical_id=entity.canonical_id,
                        canonical_name=entity.canonical_name,
                        match_method=MatchMethod.ALIAS,
                        confidence=0.90,
                        candidates=[],
                    )

        # -------------------------------------------------------------
        # Stage 3: Normalized Match (normalized string match)
        # -------------------------------------------------------------
        for entity in candidates:
            norm_canonical = normalize_entity_name(entity.canonical_name)
            if norm_raw and norm_raw == norm_canonical:
                return MatchResult(
                    canonical_id=entity.canonical_id,
                    canonical_name=entity.canonical_name,
                    match_method=MatchMethod.NORMALIZED,
                    confidence=0.95,
                    candidates=[],
                )

        # -------------------------------------------------------------
        # Stage 3.5: Normalized Alias Match
        # -------------------------------------------------------------
        for entity in candidates:
            for alias in entity.aliases:
                norm_alias = normalize_entity_name(alias)
                if norm_raw and norm_raw == norm_alias:
                    return MatchResult(
                        canonical_id=entity.canonical_id,
                        canonical_name=entity.canonical_name,
                        match_method=MatchMethod.ALIAS,
                        confidence=0.90,
                        candidates=[],
                    )

        # -------------------------------------------------------------
        # Stage 4: Fuzzy Match & Ambiguity Checking
        # -------------------------------------------------------------
        fuzzy_candidates: list[LLMFallbackCandidate] = []
        for entity in candidates:
            best_entity_score = self._compute_score(norm_raw, entity)
            if best_entity_score >= self.fuzzy_ambiguous_threshold:
                fuzzy_candidates.append(
                    LLMFallbackCandidate(
                        canonical_id=entity.canonical_id,
                        canonical_name=entity.canonical_name,
                        score=best_entity_score,
                    )
                )

        fuzzy_candidates.sort(key=lambda c: c.score, reverse=True)

        if not fuzzy_candidates:
            return MatchResult(
                canonical_id=None,
                canonical_name=None,
                match_method=MatchMethod.UNRESOLVED,
                confidence=0.0,
                candidates=[],
            )

        top = fuzzy_candidates[0]
        second = fuzzy_candidates[1] if len(fuzzy_candidates) > 1 else None

        # Check for ambiguity: if top two candidates are very close in score
        is_ambiguous = False
        if second is not None:
            if (top.score - second.score) < self.ambiguity_delta:
                is_ambiguous = True

        if is_ambiguous:
            # Ambiguous match! Try LLM Fallback if available
            if self.llm_fallback:
                fallback_res = self.llm_fallback.resolve_ambiguous(
                    raw_name=raw_name,
                    candidates=fuzzy_candidates,
                    source_context=source_context,
                )
                if fallback_res.selected_canonical_id:
                    return MatchResult(
                        canonical_id=fallback_res.selected_canonical_id,
                        canonical_name=fallback_res.canonical_name,
                        match_method=MatchMethod.LLM,
                        confidence=fallback_res.confidence,
                        candidates=fuzzy_candidates,
                    )

            # Unresolved due to ambiguity
            return MatchResult(
                canonical_id=None,
                canonical_name=None,
                match_method=MatchMethod.UNRESOLVED,
                confidence=0.0,
                candidates=fuzzy_candidates,
            )

        # High confidence single fuzzy match
        if top.score >= self.fuzzy_strong_threshold:
            return MatchResult(
                canonical_id=top.canonical_id,
                canonical_name=top.canonical_name,
                match_method=MatchMethod.FUZZY,
                confidence=top.score,
                candidates=fuzzy_candidates,
            )

        # Single candidate in 0.80 - 0.95 range
        if top.score >= self.fuzzy_ambiguous_threshold:
            return MatchResult(
                canonical_id=top.canonical_id,
                canonical_name=top.canonical_name,
                match_method=MatchMethod.FUZZY,
                confidence=top.score,
                candidates=fuzzy_candidates,
            )

        return MatchResult(
            canonical_id=None,
            canonical_name=None,
            match_method=MatchMethod.UNRESOLVED,
            confidence=0.0,
            candidates=fuzzy_candidates,
        )

    def _compute_score(self, norm_raw: str, entity: CanonicalEntity) -> float:
        """Compute the maximum similarity score between norm_raw and entity canonical name/aliases."""
        norm_canonical = normalize_entity_name(entity.canonical_name)
        max_score = self._similarity(norm_raw, norm_canonical)

        for alias in entity.aliases:
            norm_alias = normalize_entity_name(alias)
            score = self._similarity(norm_raw, norm_alias)
            if score > max_score:
                max_score = score

        return round(max_score, 2)

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Deterministic string similarity using SequenceMatcher and token overlap."""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0

        ratio = SequenceMatcher(None, a, b).ratio()

        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if tokens_a and tokens_b:
            if tokens_a == tokens_b:
                return 1.0
            if tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a):
                overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
                partial = 0.85 + (0.10 * overlap)
                return max(ratio, partial)

        return ratio
