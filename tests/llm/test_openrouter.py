"""Unit tests for OpenRouterProvider (Requirement 17)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from pydantic import BaseModel
from src.llm.openrouter import (
    OpenRouterProvider,
    OpenRouterRateLimiter,
    calculate_request_fingerprint,
)
from src.llm.exceptions import (
    AuthenticationError,
    OversizedRequestError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from src.llm.orchestrator import LLMOrchestrator
from tests.llm.test_providers import MockClientResponse
from tests.llm.test_orchestrator import DummyMockProvider


class OpenTestSchema(BaseModel):
    status: str


@pytest.mark.asyncio
async def test_openrouter_successful_response():
    provider = OpenRouterProvider(api_key="test_or_key", model="openrouter/free")
    mock_body = {
        "model": "qwen/qwen-2.5-72b-instruct",
        "choices": [{"message": {"content": "Hello from OpenRouter"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, mock_body)):
        resp = await provider.generate("hi")
        assert resp.success is True
        assert resp.provider == "openrouter"
        assert resp.text == "Hello from OpenRouter"
        assert resp.model == "qwen/qwen-2.5-72b-instruct"
        assert resp.requested_model == "openrouter/free"
        assert resp.usage.total_tokens == 20


@pytest.mark.asyncio
async def test_openrouter_api_authentication():
    provider = OpenRouterProvider(api_key="secret_token_123", model="openrouter/free")
    mock_body = {"choices": [{"message": {"content": "ok"}}]}

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value = MockClientResponse(200, mock_body)
        await provider.generate("hi")

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer secret_token_123"


@pytest.mark.asyncio
async def test_openrouter_missing_api_key():
    provider = OpenRouterProvider(api_key="", model="openrouter/free")
    assert provider.is_configured() is False

    with pytest.raises(AuthenticationError):
        await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_400_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(400, {"error": {"message": "Invalid prompt"}})):
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("hi")
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_openrouter_401_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(401, {"error": {"message": "Unauthorized"}})):
        with pytest.raises(AuthenticationError) as exc_info:
            await provider.generate("hi")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_openrouter_403_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(403, {"error": {"message": "Forbidden"}})):
        with pytest.raises(AuthenticationError) as exc_info:
            await provider.generate("hi")
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_openrouter_408_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(408, {"error": {"message": "Timeout"}})):
        with pytest.raises(TimeoutError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_413_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(413, {"error": {"message": "Too Large"}})):
        with pytest.raises(OversizedRequestError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_429_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(429, {"error": {"message": "Rate limited"}})):
        with pytest.raises(RateLimitError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_500_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(500, {"error": {"message": "Server Error"}})):
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("hi")
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_openrouter_502_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(502, {"error": {"message": "Bad Gateway"}})):
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("hi")
        assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_openrouter_503_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(503, {"error": {"message": "Service Unavailable"}})):
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("hi")
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_openrouter_timeout():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", side_effect=asyncio.TimeoutError()):
        with pytest.raises(TimeoutError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_malformed_response():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")

    class MalformedResponse(MockClientResponse):
        async def json(self):
            raise ValueError("Invalid JSON")

        async def text(self):
            return "<html>502 Bad Gateway</html>"

    with patch("aiohttp.ClientSession.post", return_value=MalformedResponse(200, {})):
        with pytest.raises(ProviderError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_missing_choices():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, {"choices": []})):
        with pytest.raises(ProviderError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_missing_content():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, {"choices": [{"message": {}}]})):
        with pytest.raises(ProviderError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_openrouter_usage_extraction():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    mock_body = {
        "choices": [{"message": {"content": "res"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, mock_body)):
        resp = await provider.generate("hi")
        assert resp.usage.prompt_tokens == 100
        assert resp.usage.completion_tokens == 50
        assert resp.usage.total_tokens == 150


@pytest.mark.asyncio
async def test_openrouter_actual_model_extraction():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    mock_body = {
        "model": "meta-llama/llama-3.1-8b-instruct",
        "choices": [{"message": {"content": "test"}}],
    }

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, mock_body)):
        resp = await provider.generate("hi")
        assert resp.model == "meta-llama/llama-3.1-8b-instruct"
        assert resp.requested_model == "openrouter/free"


@pytest.mark.asyncio
async def test_openrouter_structured_output():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free")
    mock_body = {"choices": [{"message": {"content": '{"status": "ok"}'}}]}

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value = MockClientResponse(200, mock_body)
        resp = await provider.generate("hi", response_format={"type": "json_object"})

        payload = mock_post.call_args.kwargs["json"]
        assert payload["response_format"] == {"type": "json_object"}
        assert resp.text == '{"status": "ok"}'


@pytest.mark.asyncio
async def test_openrouter_unsupported_structured_output_fallback():
    provider = OpenRouterProvider(api_key="key", model="openrouter/free", enable_cache=False)
    resp_400 = MockClientResponse(400, {"error": {"message": "response_format is unsupported for model"}})
    resp_200 = MockClientResponse(200, {"choices": [{"message": {"content": '{"status": "fallback"}'}}]})

    with patch("aiohttp.ClientSession.post", side_effect=[resp_400, resp_200]):
        resp = await provider.generate("hi", response_format={"type": "json_object"})
        assert resp.text == '{"status": "fallback"}'


def test_openrouter_api_key_redaction():
    provider = OpenRouterProvider(api_key="super_secret_key_abc", model="openrouter/free")
    redacted = provider._redact_secrets("Error occurred with key super_secret_key_abc on request")
    assert "super_secret_key_abc" not in redacted
    assert "[REDACTED_API_KEY]" in redacted


def test_openrouter_request_fingerprint():
    fp1 = calculate_request_fingerprint("openrouter", "openrouter/free", "sys", "usr")
    fp2 = calculate_request_fingerprint("openrouter", "openrouter/free", "sys", "usr")
    fp3 = calculate_request_fingerprint("openrouter", "openrouter/free", "sys", "usr_different")

    assert fp1 == fp2
    assert fp1 != fp3
    assert "api_key" not in fp1


@pytest.mark.asyncio
async def test_openrouter_daily_request_limit():
    limiter = OpenRouterRateLimiter(daily_limit=2, rpm_limit=10)
    limiter.check_and_record()
    limiter.check_and_record()

    with pytest.raises(RateLimitError) as exc_info:
        limiter.check_and_record()

    assert "daily request limit reached" in str(exc_info.value)


def test_openrouter_default_daily_limit_is_50():
    limiter = OpenRouterRateLimiter()
    assert limiter.daily_limit == 50
    assert limiter.rpm_limit == 20


def test_openrouter_provider_default_daily_limit_is_50():
    provider = OpenRouterProvider(api_key="test_key")
    assert provider.rate_limiter.daily_limit == 50
    assert provider.rate_limiter.rpm_limit == 20


@pytest.mark.asyncio
async def test_openrouter_rpm_limit():
    limiter = OpenRouterRateLimiter(daily_limit=100, rpm_limit=2)
    limiter.check_and_record()
    limiter.check_and_record()

    with pytest.raises(RateLimitError) as exc_info:
        limiter.check_and_record()

    assert "RPM limit reached" in str(exc_info.value)


def test_openrouter_provider_registration():
    p = OpenRouterProvider(api_key="test_key")
    orchestrator = LLMOrchestrator(providers=[p])
    status = orchestrator.get_health_status()
    assert "Openrouter" in status
    assert status["Openrouter"] == "Configured"


@pytest.mark.asyncio
async def test_openrouter_orchestrator_integration():
    p1 = OpenRouterProvider(api_key="key", model="openrouter/free")
    p2 = DummyMockProvider("gemini", "gemini-1.5-flash")

    # OpenRouter fails with 429, Gemini succeeds
    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(429, {"error": {"message": "Rate limit"}})):
        p2.generate_mock.return_value = MagicMock(provider="gemini", model="gemini-1.5-flash", text="Gemini ok", latency=0.1, usage=None)

        orchestrator = LLMOrchestrator(providers=[p1, p2], max_retries=1, backoff_base=0.01)
        resp = await orchestrator.generate("hi")

        assert resp.provider == "gemini"
        assert resp.text == "Gemini ok"
