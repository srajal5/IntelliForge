"""OpenRouter LLM Provider implementation supporting free models, rate limiting, and fallback."""

from __future__ import annotations

import asyncio
import hashlib
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


def calculate_request_fingerprint(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str | None = None,
) -> str:
    """Compute a deterministic SHA256 fingerprint for request deduplication.

    CRITICAL SECURITY REQUIREMENT: API keys or secrets MUST NEVER be included.
    """
    key_data = f"{provider}:{model}:{system_prompt}:{user_prompt}:{schema_name or ''}"
    return hashlib.sha256(key_data.encode("utf-8")).hexdigest()


class OpenRouterRateLimiter:
    """In-memory rate limiter protecting OpenRouter daily and RPM limits."""

    def __init__(self, daily_limit: int = 50, rpm_limit: int = 20) -> None:
        self.daily_limit = daily_limit
        self.rpm_limit = rpm_limit
        self._timestamps: list[float] = []

    def check_and_record(self) -> None:
        now = time.time()
        # Clean timestamps older than 24 hours (86400s)
        self._timestamps = [t for t in self._timestamps if now - t < 86400]

        # Check RPM (past 60s)
        rpm_count = len([t for t in self._timestamps if now - t < 60])
        if rpm_count >= self.rpm_limit:
            raise RateLimitError(
                f"OpenRouter RPM limit reached ({rpm_count}/{self.rpm_limit} requests in past minute)",
                provider="openrouter",
            )

        # Check Daily Limit (past 24h)
        daily_count = len(self._timestamps)
        if daily_count >= self.daily_limit:
            raise RateLimitError(
                f"OpenRouter daily request limit reached ({daily_count}/{self.daily_limit} requests in past 24 hours)",
                provider="openrouter",
            )

        self._timestamps.append(now)

    def reset(self) -> None:
        self._timestamps.clear()


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider targeting OpenAI-compatible REST endpoints and free models."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        daily_limit: int | None = None,
        rpm_limit: int | None = None,
        enable_cache: bool = True,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self._model = model if model is not None else settings.openrouter_model
        self.base_url = (base_url if base_url is not None else settings.openrouter_base_url).rstrip("/")

        d_limit = daily_limit if daily_limit is not None else settings.openrouter_daily_request_limit
        r_limit = rpm_limit if rpm_limit is not None else settings.openrouter_rpm_limit
        self.rate_limiter = OpenRouterRateLimiter(daily_limit=d_limit, rpm_limit=r_limit)

        self.enable_cache = enable_cache
        self._cache: dict[str, LLMResponse] = {}

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        """Return True if a valid, non-placeholder API key is set."""
        if not self.api_key or not self.api_key.strip():
            return False
        return not self.api_key.strip().startswith("your_")

    def _redact_secrets(self, text: str) -> str:
        """Strip API key from exception/log messages if present."""
        if self.api_key and self.api_key in text:
            return text.replace(self.api_key, "[REDACTED_API_KEY]")
        return text

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute async generation call against OpenRouter API."""
        if not self.is_configured():
            raise AuthenticationError(
                "OpenRouter API key is missing or unconfigured.", provider=self.name
            )

        # 1. Deduplication cache check
        fingerprint = calculate_request_fingerprint(
            provider=self.name,
            model=self._model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            schema_name=str(response_format) if response_format else None,
        )
        if self.enable_cache and fingerprint in self._cache:
            logger.info("openrouter_request_cache_hit", fingerprint=fingerprint)
            cached_resp = self._cache[fingerprint]
            return cached_resp.model_copy()

        # 2. Check local rate limit (RPM & Daily limit)
        self.rate_limiter.check_and_record()

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ai-intelligence-pipeline",
            "X-Title": "AI Intelligence Pipeline",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        start_time = time.time()

        try:
            timeout = aiohttp.ClientTimeout(total=60.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    latency = time.time() - start_time
                    status = resp.status

                    try:
                        response_json = await resp.json()
                    except Exception:
                        response_text = await resp.text()
                        if status == 200:
                            raise ProviderError(
                                f"OpenRouter returned malformed JSON response: {response_text[:200]}",
                                provider=self.name,
                            )
                        response_json = {"error": {"message": response_text}}

                    # Handle 400 unsupported structured output fallback
                    if status == 400 and response_format:
                        err_msg = str(response_json).lower()
                        if "response_format" in err_msg or "structured" in err_msg or "schema" in err_msg:
                            logger.warning(
                                "openrouter_structured_output_unsupported_falling_back_to_text",
                                provider=self.name,
                            )
                            payload.pop("response_format", None)
                            async with session.post(url, headers=headers, json=payload) as fallback_resp:
                                status = fallback_resp.status
                                response_json = await fallback_resp.json()

                    if status == 200:
                        choices = response_json.get("choices")
                        if not choices or not isinstance(choices, list) or len(choices) == 0:
                            raise ProviderError(
                                "OpenRouter response missing valid choices array.",
                                provider=self.name,
                            )

                        message_obj = choices[0].get("message", {})
                        text_content = message_obj.get("content")
                        if text_content is None:
                            raise ProviderError(
                                "OpenRouter choice message missing content field.",
                                provider=self.name,
                            )

                        # Capture actual underlying model returned by OpenRouter if available
                        actual_model = response_json.get("model") or self._model

                        # Extract token usage if available
                        usage_obj = response_json.get("usage")
                        usage = None
                        if usage_obj and isinstance(usage_obj, dict):
                            usage = TokenUsage(
                                prompt_tokens=usage_obj.get("prompt_tokens"),
                                completion_tokens=usage_obj.get("completion_tokens"),
                                total_tokens=usage_obj.get("total_tokens"),
                            )

                        result_response = LLMResponse(
                            provider=self.name,
                            model=actual_model,
                            requested_model=self._model,
                            text=text_content,
                            usage=usage,
                            latency=latency,
                            success=True,
                        )

                        if self.enable_cache:
                            self._cache[fingerprint] = result_response

                        return result_response

                    # Error handling by status code
                    err_detail = response_json.get("error", {}).get("message", str(response_json))
                    clean_err = self._redact_secrets(str(err_detail))

                    if status == 400:
                        raise ProviderError(
                            f"OpenRouter 400 Bad Request: {clean_err}",
                            provider=self.name,
                            status_code=400,
                        )
                    elif status in (401, 403):
                        raise AuthenticationError(
                            f"OpenRouter Auth Failure ({status}): {clean_err}",
                            provider=self.name,
                            status_code=status,
                        )
                    elif status == 408:
                        raise TimeoutError(
                            f"OpenRouter 408 Timeout: {clean_err}", provider=self.name
                        )
                    elif status == 413:
                        raise OversizedRequestError(
                            f"OpenRouter 413 Oversized Request: {clean_err}", provider=self.name
                        )
                    elif status == 429:
                        raise RateLimitError(
                            f"OpenRouter 429 Rate Limit: {clean_err}", provider=self.name
                        )
                    elif status in (500, 502, 503, 504):
                        raise ProviderError(
                            f"OpenRouter {status} Server Error: {clean_err}",
                            provider=self.name,
                            status_code=status,
                        )
                    else:
                        raise ProviderError(
                            f"OpenRouter Unexpected HTTP {status}: {clean_err}",
                            provider=self.name,
                            status_code=status,
                        )

        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
            raise TimeoutError("OpenRouter request connection timed out", provider=self.name)
        except aiohttp.ClientError as exc:
            raise ProviderError(
                f"OpenRouter HTTP network error: {self._redact_secrets(str(exc))}",
                provider=self.name,
            )
