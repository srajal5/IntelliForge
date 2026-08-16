"""Abstract LLM Provider interface definition."""

from __future__ import annotations

from abc import ABC, abstractmethod
from src.llm.models import LLMResponse


class LLMProvider(ABC):
    """Abstract base class for all LLM service providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider identifier (e.g. 'gemini', 'groq', 'deepseek')."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Return model identifier used by the provider."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required API keys and configuration exist."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Execute async generation call and return a standardized LLMResponse.

        Raises:
            RateLimitError: On HTTP 429
            OversizedRequestError: On HTTP 413
            AuthenticationError: On HTTP 401/403
            TimeoutError: On HTTP 408 or socket timeout
            ProviderError: On HTTP 5xx or general provider failure
        """
        pass
