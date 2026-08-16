"""Gemini LLM Provider implementation using REST API via aiohttp for explicit status handling."""

from __future__ import annotations

import asyncio
import time
from typing import Any
import aiohttp

from src.config.settings import get_settings
from src.llm.exceptions import (
    AuthenticationError,
    OversizedRequestError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from src.llm.models import LLMResponse, TokenUsage
from src.llm.provider import LLMProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Primary LLM provider backed by Google Gemini API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self._model = model or settings.gemini_model

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_gemini_api_key_here")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Execute async generation call to Gemini REST API."""
        if not self.is_configured():
            raise AuthenticationError("Gemini API key is not configured", provider=self.name)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self.api_key}"

        contents: list[dict[str, Any]] = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow your system instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        start_time = time.perf_counter()

        try:
            timeout = aiohttp.ClientTimeout(total=30.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    status = resp.status
                    response_json = await resp.json()

                    if status == 200:
                        latency = time.perf_counter() - start_time
                        text = ""
                        candidates = response_json.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            text = "".join(p.get("text", "") for p in parts)

                        usage_meta = response_json.get("usageMetadata", {})
                        usage = TokenUsage(
                            prompt_tokens=usage_meta.get("promptTokenCount"),
                            completion_tokens=usage_meta.get("candidatesTokenCount"),
                            total_tokens=usage_meta.get("totalTokenCount"),
                        )

                        return LLMResponse(
                            provider=self.name,
                            model=self._model,
                            text=text,
                            usage=usage,
                            latency=round(latency, 4),
                            success=True,
                        )

                    # Handle explicit HTTP error status codes
                    error_msg = response_json.get("error", {}).get("message", f"Gemini HTTP {status}")
                    logger.warning("gemini_http_error", status=status, error=error_msg)

                    if status == 429:
                        raise RateLimitError(f"Gemini Rate Limit (429): {error_msg}", provider=self.name)
                    if status == 413:
                        raise OversizedRequestError(f"Gemini Oversized Payload (413): {error_msg}", provider=self.name)
                    if status in (401, 403):
                        raise AuthenticationError(f"Gemini Auth Error ({status}): {error_msg}", provider=self.name, status_code=status)
                    if status in (408, 504):
                        raise TimeoutError(f"Gemini Timeout ({status}): {error_msg}", provider=self.name)
                    if status in (500, 502, 503):
                        raise ProviderError(f"Gemini Server Error ({status}): {error_msg}", provider=self.name, status_code=status)

                    raise ProviderError(f"Gemini Status Error ({status}): {error_msg}", provider=self.name, status_code=status)

        except asyncio.TimeoutError as exc:
            raise TimeoutError("Gemini client connection timed out", provider=self.name) from exc
        except aiohttp.ClientError as exc:
            raise ProviderError(f"Gemini network connection error: {exc}", provider=self.name) from exc
