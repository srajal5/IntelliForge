"""Unit test for Entity resolution LLM fallback integration (Requirement 23)."""

import pytest
from unittest.mock import AsyncMock

from src.entity.fallback_interface import (
    LLMFallbackCandidate,
    LLMFallbackResult,
    LLMOrchestratorEntityFallback,
)
from src.llm.orchestrator import LLMOrchestrator


@pytest.mark.asyncio
async def test_entity_fallback_resolution_mock_llm():
    # 1. Setup candidates for ambiguous entity 'DeepMind'
    candidates = [
        LLMFallbackCandidate(canonical_id="entity_google_deepmind", canonical_name="Google DeepMind", score=0.88),
        LLMFallbackCandidate(canonical_id="entity_deepmind_health", canonical_name="DeepMind Health", score=0.86),
    ]

    # 2. Mock LLM Orchestrator return value
    mock_orchestrator = AsyncMock(spec=LLMOrchestrator)
    mock_orchestrator.extract_structured.return_value = LLMFallbackResult(
        selected_canonical_id="entity_google_deepmind",
        canonical_name="Google DeepMind",
        confidence=0.95,
        reason="Source context explicitly mentions parent company Google",
    )

    # 3. Initialize entity fallback with mock orchestrator
    fallback = LLMOrchestratorEntityFallback(orchestrator=mock_orchestrator)

    # 4. Perform resolution
    result = await fallback.async_resolve_ambiguous(
        raw_name="DeepMind",
        candidates=candidates,
        source_context={"url": "https://deepmind.google", "title": "Google DeepMind Research"},
    )

    # 5. Assert canonical entity resolution
    assert result.selected_canonical_id == "entity_google_deepmind"
    assert result.canonical_name == "Google DeepMind"
    assert result.confidence == 0.95
    assert "Google" in result.reason
    assert mock_orchestrator.extract_structured.call_count == 1
