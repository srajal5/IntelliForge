"""Groq LLM Provider implementation using REST API via aiohttp for explicit status handling."""

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


class GroqProvider(LLMProvider):
    """First fallback LLM provider backed by Groq API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.groq_api_key
        self._model = model or settings.groq_model

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_groq_api_key_here")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Execute async generation call to Groq OpenAI-compatible REST API."""
        if not self.is_configured():
            raise AuthenticationError("Groq API key is not configured", provider=self.name)

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start_time = time.perf_counter()

        try:
            timeout = aiohttp.ClientTimeout(total=30.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    status = resp.status
                    response_json = await resp.json()

                    if status == 200:
                        latency = time.perf_counter() - start_time
                        choices = response_json.get("choices", [])
                        text = choices[0]["message"]["content"] if choices else ""

                        usage_meta = response_json.get("usage", {})
                        usage = TokenUsage(
                            prompt_tokens=usage_meta.get("prompt_tokens"),
                            completion_tokens=usage_meta.get("completion_tokens"),
                            total_tokens=usage_meta.get("total_tokens"),
                        )

                        return LLMResponse(
                            provider=self.name,
                            model=self._model,
                            text=text,
                            usage=usage,
                            latency=round(latency, 4),
                            success=True,
                        )

                    error_msg = response_json.get("error", {}).get("message", f"Groq HTTP {status}")
                    logger.warning("groq_http_error", status=status, error=error_msg)

                    if status == 429:
                        raise RateLimitError(f"Groq Rate Limit (429): {error_msg}", provider=self.name)
                    if status == 413:
                        raise OversizedRequestError(f"Groq Oversized Payload (413): {error_msg}", provider=self.name)
                    if status in (401, 403):
                        raise AuthenticationError(f"Groq Auth Error ({status}): {error_msg}", provider=self.name, status_code=status)
                    if status in (408, 504):
                        raise TimeoutError(f"Groq Timeout ({status}): {error_msg}", provider=self.name)
                    if status in (500, 502, 503):
                        raise ProviderError(f"Groq Server Error ({status}): {error_msg}", provider=self.name, status_code=status)

                    raise ProviderError(f"Groq Status Error ({status}): {error_msg}", provider=self.name, status_code=status)

        except asyncio.TimeoutError as exc:
            raise TimeoutError("Groq client connection timed out", provider=self.name) from exc
        except aiohttp.ClientError as exc:
            raise ProviderError(f"Groq network connection error: {exc}", provider=self.name) from exc
