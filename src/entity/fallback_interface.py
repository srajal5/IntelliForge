"""LLM Fallback Interface for ambiguous Entity Resolution."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class LLMFallbackCandidate(BaseModel):
    """Candidate entity passed to LLM for resolution."""

    canonical_id: str
    canonical_name: str
    score: float = 0.0


class LLMFallbackResult(BaseModel):
    """Result returned by LLM fallback decision."""

    selected_canonical_id: str | None = None
    canonical_name: str | None = None
    confidence: float = 0.0
    reason: str = "No resolution attempted"


class EntityLLMFallbackInterface(ABC):
    """Abstract interface for LLM fallback resolution of ambiguous entities."""

    @abstractmethod
    def resolve_ambiguous(
        self,
        raw_name: str,
        candidates: list[LLMFallbackCandidate],
        source_context: dict[str, Any] | None = None,
    ) -> LLMFallbackResult:
        """Resolve an ambiguous raw entity name against a set of candidate canonical entities."""
        pass


class MockEntityLLMFallback(EntityLLMFallbackInterface):
    """Mock/No-op implementation of EntityLLMFallbackInterface for Phase 6 testing and default fallback."""

    def __init__(self, default_response: LLMFallbackResult | None = None):
        self._default_response = default_response or LLMFallbackResult(
            selected_canonical_id=None,
            canonical_name=None,
            confidence=0.0,
            reason="Mock LLM fallback — unresolved by default in Phase 6",
        )

    def resolve_ambiguous(
        self,
        raw_name: str,
        candidates: list[LLMFallbackCandidate],
        source_context: dict[str, Any] | None = None,
    ) -> LLMFallbackResult:
        """Return pre-configured mock response or default unresolved response."""
        return self._default_response


class LLMOrchestratorEntityFallback(EntityLLMFallbackInterface):
    """Production LLM implementation of EntityLLMFallbackInterface backed by LLMOrchestrator."""

    def __init__(self, orchestrator: Any = None) -> None:
        from src.llm.orchestrator import LLMOrchestrator
        self.orchestrator = orchestrator or LLMOrchestrator()

    def resolve_ambiguous(
        self,
        raw_name: str,
        candidates: list[LLMFallbackCandidate],
        source_context: dict[str, Any] | None = None,
    ) -> LLMFallbackResult:
        """Synchronous wrapper for resolve_ambiguous."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Running inside existing loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.async_resolve_ambiguous(raw_name, candidates, source_context)
                    )
                    return future.result(timeout=30.0)
            else:
                return asyncio.run(self.async_resolve_ambiguous(raw_name, candidates, source_context))
        except Exception as exc:
            return LLMFallbackResult(
                selected_canonical_id=None,
                canonical_name=None,
                confidence=0.0,
                reason=f"LLM fallback resolution failed: {exc}",
            )

    async def async_resolve_ambiguous(
        self,
        raw_name: str,
        candidates: list[LLMFallbackCandidate],
        source_context: dict[str, Any] | None = None,
    ) -> LLMFallbackResult:
        """Asynchronously resolve ambiguous entity using LLMOrchestrator."""
        import json
        from src.llm.prompts import ENTITY_RESOLUTION_V1

        candidates_json = json.dumps([c.model_dump() for c in candidates], indent=2)
        prompt = ENTITY_RESOLUTION_V1.format(
            raw_name=raw_name,
            candidates_json=candidates_json,
            source_context=json.dumps(source_context or {}),
        )

        try:
            result = await self.orchestrator.extract_structured(
                prompt=prompt,
                target_schema=LLMFallbackResult,
                system_prompt="You are an entity resolution engine. Follow instructions and return valid JSON.",
            )
            return result
        except Exception as exc:
            return LLMFallbackResult(
                selected_canonical_id=None,
                canonical_name=None,
                confidence=0.0,
                reason=f"LLM fallback orchestrator error: {exc}",
            )

