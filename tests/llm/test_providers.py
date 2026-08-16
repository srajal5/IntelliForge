"""Unit tests for Gemini, Groq, and DeepSeek individual provider implementations."""

import pytest
from unittest.mock import AsyncMock, patch

from src.llm.gemini import GeminiProvider
from src.llm.groq import GroqProvider
from src.llm.deepseek import DeepSeekProvider
from src.llm.exceptions import (
    AuthenticationError,
    OversizedRequestError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)


class MockClientResponse:
    def __init__(self, status: int, json_data: dict):
        self.status = status
        self._json_data = json_data

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.asyncio
async def test_gemini_is_configured():
    provider = GeminiProvider(api_key="test_gemini_key")
    assert provider.is_configured() is True

    unconfigured = GeminiProvider(api_key="")
    assert unconfigured.is_configured() is False


@pytest.mark.asyncio
async def test_gemini_unconfigured_raises_auth_error():
    provider = GeminiProvider(api_key="")
    with pytest.raises(AuthenticationError):
        await provider.generate("hello")


@pytest.mark.asyncio
async def test_gemini_success_200():
    provider = GeminiProvider(api_key="test_key", model="gemini-1.5-flash")

    mock_resp = {
        "candidates": [{"content": {"parts": [{"text": "Hello world"}]}}],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "totalTokenCount": 15,
        },
    }

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, mock_resp)):
        response = await provider.generate("hi")

        assert response.success is True
        assert response.provider == "gemini"
        assert response.text == "Hello world"
        assert response.usage.prompt_tokens == 10
        assert response.usage.total_tokens == 15


@pytest.mark.asyncio
async def test_gemini_429_rate_limit():
    provider = GeminiProvider(api_key="test_key", model="gemini-1.5-flash")

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(429, {"error": {"message": "Quota exceeded"}})):
        with pytest.raises(RateLimitError) as exc_info:
            await provider.generate("hi")
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_gemini_413_oversized():
    provider = GeminiProvider(api_key="test_key", model="gemini-1.5-flash")

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(413, {"error": {"message": "Payload too large"}})):
        with pytest.raises(OversizedRequestError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_gemini_500_server_error():
    provider = GeminiProvider(api_key="test_key", model="gemini-1.5-flash")

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(500, {"error": {"message": "Internal error"}})):
        with pytest.raises(ProviderError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_groq_success_200():
    provider = GroqProvider(api_key="test_groq_key", model="llama-3.3-70b-versatile")

    mock_resp = {
        "choices": [{"message": {"content": "Groq response"}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
    }

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, mock_resp)):
        response = await provider.generate("hi groq")

        assert response.success is True
        assert response.provider == "groq"
        assert response.text == "Groq response"
        assert response.usage.total_tokens == 12


@pytest.mark.asyncio
async def test_groq_401_auth_error():
    provider = GroqProvider(api_key="test_groq_key", model="llama-3.3-70b-versatile")

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(401, {"error": {"message": "Invalid key"}})):
        with pytest.raises(AuthenticationError):
            await provider.generate("hi")


@pytest.mark.asyncio
async def test_deepseek_success_200():
    provider = DeepSeekProvider(api_key="test_ds_key", model="deepseek-chat")

    mock_resp = {
        "choices": [{"message": {"content": "DeepSeek response"}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
    }

    with patch("aiohttp.ClientSession.post", return_value=MockClientResponse(200, mock_resp)):
        response = await provider.generate("hi deepseek")

        assert response.success is True
        assert response.provider == "deepseek"
        assert response.text == "DeepSeek response"
        assert response.usage.total_tokens == 25
