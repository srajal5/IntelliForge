"""Custom exception hierarchy for the LLM Orchestration Engine."""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for all LLM errors."""

    def __init__(self, message: str, provider: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class RateLimitError(LLMError):
    """Raised on HTTP 429 (Rate Limit Exceeded)."""

    def __init__(self, message: str = "Rate limit exceeded (429)", provider: str | None = None):
        super().__init__(message, provider=provider, status_code=429)


class OversizedRequestError(LLMError):
    """Raised on HTTP 413 (Payload / Request Too Large)."""

    def __init__(self, message: str = "Request size exceeds provider limit (413)", provider: str | None = None):
        super().__init__(message, provider=provider, status_code=413)


class AuthenticationError(LLMError):
    """Raised on HTTP 401 or 403 (Invalid API key or unauthorized access)."""

    def __init__(self, message: str = "Authentication failed (401/403)", provider: str | None = None, status_code: int = 401):
        super().__init__(message, provider=provider, status_code=status_code)


class TimeoutError(LLMError):
    """Raised on HTTP 408 or network socket timeouts."""

    def __init__(self, message: str = "Request timed out (408)", provider: str | None = None):
        super().__init__(message, provider=provider, status_code=408)


class ProviderError(LLMError):
    """Raised on HTTP 5xx or unrecoverable provider status errors."""

    def __init__(self, message: str = "LLM provider internal error", provider: str | None = None, status_code: int | None = 500):
        super().__init__(message, provider=provider, status_code=status_code)


class AllProvidersFailedError(LLMError):
    """Raised when all configured providers in the fallback chain fail."""

    def __init__(self, message: str = "All LLM providers in fallback chain failed", errors: dict[str, str] | None = None):
        super().__init__(message)
        self.errors = errors or {}


class StructuredOutputError(LLMError):
    """Raised when LLM response cannot be parsed or validated against the target Pydantic schema."""

    def __init__(self, message: str = "Failed to parse or validate structured LLM output", raw_text: str | None = None):
        super().__init__(message)
        self.raw_text = raw_text
