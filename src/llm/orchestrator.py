"""Production LLM Orchestrator managing fallbacks, retries, 429/413 handling, structured extraction, and telemetry."""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar
from pydantic import BaseModel

from src.config.settings import get_settings
from src.llm.deepseek import DeepSeekProvider
from src.llm.exceptions import (
    AllProvidersFailedError,
    AuthenticationError,
    OversizedRequestError,
    ProviderError,
    RateLimitError,
    StructuredOutputError,
    TimeoutError,
)
from src.llm.gemini import GeminiProvider
from src.llm.groq import GroqProvider
from src.llm.models import LLMResponse
from src.llm.openrouter import OpenRouterProvider
from src.llm.parser import JSONParser
from src.llm.provider import LLMProvider
from src.llm.retry import execute_with_retry
from src.llm.size_manager import RequestSizeManager
from src.llm.telemetry import LLMTelemetryTracker
from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def _instantiate_provider(name: str) -> LLMProvider | None:
    n = name.strip().lower()
    if n == "openrouter":
        return OpenRouterProvider()
    elif n == "gemini":
        return GeminiProvider()
    elif n == "groq":
        return GroqProvider()
    elif n == "deepseek":
        return DeepSeekProvider()
    return None


def _build_default_providers() -> list[LLMProvider]:
    settings = get_settings()
    primary = settings.llm_primary_provider
    fallbacks = [f.strip() for f in settings.llm_fallback_providers.split(",") if f.strip()]

    names = []
    if primary and primary.strip():
        names.append(primary.strip())
    names.extend(fallbacks)

    unique_names: list[str] = []
    for n in names:
        if n.lower() not in [x.lower() for x in unique_names]:
            unique_names.append(n)

    providers: list[LLMProvider] = []
    for name in unique_names:
        p = _instantiate_provider(name)
        if p:
            providers.append(p)
    return providers or [OpenRouterProvider(), GeminiProvider(), GroqProvider(), DeepSeekProvider()]


class LLMOrchestrator:
    """Orchestrates async generation calls across primary and fallback LLM providers."""

    def __init__(
        self,
        providers: list[LLMProvider] | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
        backoff_max: float | None = None,
        concurrency: int | None = None,
    ) -> None:
        settings = get_settings()
        self.providers = providers if providers is not None else _build_default_providers()
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.backoff_base = backoff_base if backoff_base is not None else settings.llm_backoff_base
        self.backoff_max = backoff_max if backoff_max is not None else settings.llm_backoff_max

        concurrency_limit = concurrency if concurrency is not None else settings.llm_concurrency
        self.semaphore = asyncio.Semaphore(max(1, concurrency_limit))

        self.size_manager = RequestSizeManager()
        self.telemetry = LLMTelemetryTracker()

    def get_health_status(self) -> dict[str, str]:
        """Report configuration status of all registered LLM providers."""
        status = {}
        for provider in self.providers:
            status[provider.name.capitalize()] = (
                "Configured" if provider.is_configured() else "Not configured"
            )
        return status

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Execute a text generation call through the provider fallback chain."""
        async with self.semaphore:
            # 1. Pre-check request size
            effective_prompt = prompt
            if self.size_manager.is_oversized(prompt):
                effective_prompt = self.size_manager.reduce_prompt(prompt)

            provider_errors: dict[str, str] = {}

            # 2. Iterate through fallback sequence (Gemini -> Groq -> DeepSeek)
            for provider in self.providers:
                if not provider.is_configured():
                    logger.info("skipping_unconfigured_provider", provider=provider.name)
                    provider_errors[provider.name] = "Provider not configured"
                    continue

                attempts = 0

                async def _call_provider() -> LLMResponse:
                    nonlocal attempts, effective_prompt
                    attempts += 1
                    return await provider.generate(
                        prompt=effective_prompt,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )

                try:
                    response = await execute_with_retry(
                        coro_fn=_call_provider,
                        provider_name=provider.name,
                        max_retries=self.max_retries,
                        backoff_base=self.backoff_base,
                        backoff_max=self.backoff_max,
                    )
                    response.attempts = attempts

                    # Record telemetry
                    self.telemetry.record_execution(
                        provider=provider.name,
                        model=provider.model,
                        attempts=attempts,
                        success=True,
                        latency=response.latency,
                        input_chars=len(effective_prompt),
                        output_chars=len(response.text),
                        usage=response.usage,
                    )
                    return response

                except OversizedRequestError as exc:
                    # 413 handling: Try reducing prompt further for one more retry on same provider
                    logger.warning("oversized_request_detected", provider=provider.name, error=str(exc))
                    further_reduced = self.size_manager.reduce_prompt(
                        effective_prompt,
                        limit=max(500, self.size_manager.max_input_chars // 2),
                    )
                    if further_reduced != effective_prompt:
                        effective_prompt = further_reduced
                        try:
                            resp = await provider.generate(
                                prompt=effective_prompt,
                                system_prompt=system_prompt,
                                max_tokens=max_tokens,
                                temperature=temperature,
                            )
                            self.telemetry.record_execution(
                                provider=provider.name,
                                model=provider.model,
                                attempts=attempts + 1,
                                success=True,
                                latency=resp.latency,
                                input_chars=len(effective_prompt),
                                output_chars=len(resp.text),
                                usage=resp.usage,
                            )
                            return resp
                        except Exception as e:
                            logger.error("oversized_retry_failed", provider=provider.name, error=str(e))

                    provider_errors[provider.name] = f"413 Oversized Request: {exc}"
                    self.telemetry.record_execution(
                        provider=provider.name,
                        model=provider.model,
                        attempts=attempts,
                        success=False,
                        latency=0.0,
                        input_chars=len(effective_prompt),
                        error_category="OversizedRequestError",
                    )
                    logger.warning("falling_back_from_oversized_provider", failed_provider=provider.name)

                except (RateLimitError, TimeoutError, ProviderError, AuthenticationError) as exc:
                    provider_errors[provider.name] = str(exc)
                    self.telemetry.record_execution(
                        provider=provider.name,
                        model=provider.model,
                        attempts=attempts,
                        success=False,
                        latency=0.0,
                        input_chars=len(effective_prompt),
                        error_category=type(exc).__name__,
                    )
                    logger.warning("llm_provider_failed_falling_back", provider=provider.name, error=str(exc))

                except Exception as exc:
                    provider_errors[provider.name] = f"Unexpected error: {exc}"
                    self.telemetry.record_execution(
                        provider=provider.name,
                        model=provider.model,
                        attempts=attempts,
                        success=False,
                        latency=0.0,
                        input_chars=len(effective_prompt),
                        error_category=type(exc).__name__,
                    )
                    logger.error("unexpected_provider_error", provider=provider.name, error=str(exc))

            raise AllProvidersFailedError(
                "All configured LLM providers in fallback chain failed",
                errors=provider_errors,
            )

    async def extract_structured(
        self,
        prompt: str,
        target_schema: type[T],
        system_prompt: str = "",
        context: dict[str, Any] | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> T:
        """Extract structured JSON from LLM generation and validate against Pydantic schema."""
        full_prompt = prompt
        if context:
            context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
            full_prompt = f"{prompt}\n\nContext Information:\n{context_str}"

        # 1. Generate text response
        response = await self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # 2. Attempt parsing and validation
        try:
            structured_obj = JSONParser.extract_structured(
                text=response.text,
                target_schema=target_schema,
                context=context,
            )
            return structured_obj
        except StructuredOutputError as exc:
            logger.warning("structured_extraction_parse_failed_attempting_correction", error=str(exc))
            # Correction prompt attempt
            correction_prompt = (
                f"{full_prompt}\n\n"
                f"PREVIOUS RESPONSE WAS INVALID AND COULD NOT BE PARSED ACCORDING TO SCHEMA.\n"
                f"Validation Error: {exc.message}\n"
                f"Please fix and output ONLY valid JSON matching the exact schema."
            )
            retry_response = await self.generate(
                prompt=correction_prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return JSONParser.extract_structured(
                text=retry_response.text,
                target_schema=target_schema,
                context=context,
            )
