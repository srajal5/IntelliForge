"""Unit tests for LLMOrchestrator fallback, retries, 413, and concurrency."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.llm.orchestrator import LLMOrchestrator
from src.llm.provider import LLMProvider
from src.llm.models import LLMResponse, TokenUsage
from src.llm.exceptions import (
    AllProvidersFailedError,
    AuthenticationError,
    OversizedRequestError,
    ProviderError,
    RateLimitError,
)


class DummyMockProvider(LLMProvider):
    def __init__(self, name: str, model: str, configured: bool = True):
        self._name = name
        self._model = model
        self._configured = configured
        self.generate_mock = AsyncMock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return self._configured

    async def generate(self, prompt: str, system_prompt: str = "", max_tokens: int = 2048, temperature: float = 0.0) -> LLMResponse:
        return await self.generate_mock(prompt=prompt, system_prompt=system_prompt, max_tokens=max_tokens, temperature=temperature)


@pytest.mark.asyncio
async def test_orchestrator_gemini_primary_success():
    p1 = DummyMockProvider("gemini", "gemini-1.5-flash")
    p2 = DummyMockProvider("groq", "llama-3.3-70b-versatile")
    p3 = DummyMockProvider("deepseek", "deepseek-chat")

    p1.generate_mock.return_value = LLMResponse(
        provider="gemini",
        model="gemini-1.5-flash",
        text="Primary Gemini Output",
        usage=TokenUsage(total_tokens=10),
    )

    orchestrator = LLMOrchestrator(providers=[p1, p2, p3], max_retries=1)
    response = await orchestrator.generate("hello")

    assert response.provider == "gemini"
    assert response.text == "Primary Gemini Output"
    assert p1.generate_mock.call_count == 1
    assert p2.generate_mock.call_count == 0


@pytest.mark.asyncio
async def test_orchestrator_fallback_gemini_to_groq():
    p1 = DummyMockProvider("gemini", "gemini-1.5-flash")
    p2 = DummyMockProvider("groq", "llama-3.3-70b-versatile")
    p3 = DummyMockProvider("deepseek", "deepseek-chat")

    # Gemini fails with 500
    p1.generate_mock.side_effect = ProviderError("Gemini down", provider="gemini")
    # Groq succeeds
    p2.generate_mock.return_value = LLMResponse(
        provider="groq",
        model="llama-3.3-70b-versatile",
        text="Groq Fallback Output",
    )

    orchestrator = LLMOrchestrator(providers=[p1, p2, p3], max_retries=1, backoff_base=0.01)
    response = await orchestrator.generate("hello")

    assert response.provider == "groq"
    assert response.text == "Groq Fallback Output"
    assert p1.generate_mock.call_count == 1
    assert p2.generate_mock.call_count == 1
    assert p3.generate_mock.call_count == 0


@pytest.mark.asyncio
async def test_orchestrator_fallback_gemini_groq_to_deepseek():
    p1 = DummyMockProvider("gemini", "gemini-1.5-flash")
    p2 = DummyMockProvider("groq", "llama-3.3-70b-versatile")
    p3 = DummyMockProvider("deepseek", "deepseek-chat")

    p1.generate_mock.side_effect = RateLimitError("Gemini 429", provider="gemini")
    p2.generate_mock.side_effect = ProviderError("Groq 500", provider="groq")
    p3.generate_mock.return_value = LLMResponse(
        provider="deepseek",
        model="deepseek-chat",
        text="DeepSeek Final Fallback",
    )

    orchestrator = LLMOrchestrator(providers=[p1, p2, p3], max_retries=1, backoff_base=0.01)
    response = await orchestrator.generate("hello")

    assert response.provider == "deepseek"
    assert response.text == "DeepSeek Final Fallback"


@pytest.mark.asyncio
async def test_orchestrator_all_providers_failed():
    p1 = DummyMockProvider("gemini", "gemini-1.5-flash")
    p2 = DummyMockProvider("groq", "llama-3.3-70b-versatile")
    p3 = DummyMockProvider("deepseek", "deepseek-chat")

    p1.generate_mock.side_effect = ProviderError("Gemini 500", provider="gemini")
    p2.generate_mock.side_effect = RateLimitError("Groq 429", provider="groq")
    p3.generate_mock.side_effect = AuthenticationError("DeepSeek 401", provider="deepseek")

    orchestrator = LLMOrchestrator(providers=[p1, p2, p3], max_retries=1, backoff_base=0.01)

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await orchestrator.generate("hello")

    assert len(exc_info.value.errors) == 3


@pytest.mark.asyncio
async def test_orchestrator_concurrency_semaphore():
    p1 = DummyMockProvider("gemini", "gemini-1.5-flash")
    active_count = 0
    max_observed = 0

    async def _mock_gen(*args, **kwargs):
        nonlocal active_count, max_observed
        active_count += 1
        if active_count > max_observed:
            max_observed = active_count
        await asyncio.sleep(0.05)
        active_count -= 1
        return LLMResponse(provider="gemini", model="gemini-1.5-flash", text="ok")

    p1.generate_mock.side_effect = _mock_gen
    orchestrator = LLMOrchestrator(providers=[p1], max_retries=1, concurrency=2)

    tasks = [orchestrator.generate(f"prompt {i}") for i in range(5)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 5
    assert max_observed <= 2
