"""Data models for LLM requests, responses, token usage, and telemetry."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token consumption metrics reported by an LLM provider."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class LLMRequest(BaseModel):
    """Request envelope passed to an LLM provider."""

    prompt: str = Field(..., min_length=1, description="Main user/content prompt.")
    system_prompt: str = Field(default="", description="Optional system instructions.")
    max_tokens: int = Field(default=2048, ge=1, le=16384, description="Max token generation limit.")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature.")
    context: dict[str, Any] | None = Field(default=None, description="Optional metadata/context.")


class LLMResponse(BaseModel):
    """Standardized response object returned by all LLM providers."""

    provider: str = Field(..., description="Name of provider (openrouter, gemini, groq, deepseek).")
    model: str = Field(..., description="Actual model identifier used or returned for generation.")
    requested_model: str | None = Field(default=None, description="Requested model slug if distinct from actual model.")
    text: str = Field(default="", description="Raw response text.")
    parsed_data: Any | None = Field(default=None, description="Parsed Pydantic model or dict.")
    usage: TokenUsage | None = Field(default=None, description="Token usage metrics if available.")
    latency: float = Field(default=0.0, ge=0.0, description="Request latency in seconds.")
    attempts: int = Field(default=1, ge=1, description="Number of attempts taken.")
    success: bool = Field(default=True, description="Whether the generation succeeded.")
    error: str | None = Field(default=None, description="Error message if generation failed.")

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class TelemetryData(BaseModel):
    """Telemetry record for tracking LLM operations and performance."""

    provider: str
    model: str
    attempts: int
    success: bool
    latency: float
    error_category: str | None = None
    input_chars: int = 0
    output_chars: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")
