"""Request size manager for estimating input size, detecting oversized inputs, and chunking/reducing prompts."""

from __future__ import annotations

import re
from src.config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RequestSizeManager:
    """Estimates input size and manages prompt reduction/chunking for LLM requests."""

    def __init__(self, max_input_chars: int | None = None) -> None:
        settings = get_settings()
        self.max_input_chars = max_input_chars or settings.llm_max_input_chars

    def estimate_size(self, text: str) -> int:
        """Estimate the character length of an input string."""
        return len(text) if text else 0

    def is_oversized(self, text: str, limit: int | None = None) -> bool:
        """Check if input text exceeds the maximum character threshold."""
        effective_limit = limit or self.max_input_chars
        return self.estimate_size(text) > effective_limit

    def reduce_prompt(self, prompt: str, limit: int | None = None) -> str:
        """Intelligently reduce an oversized prompt by trimming at natural boundaries (paragraphs/lines)."""
        effective_limit = limit or self.max_input_chars

        if not self.is_oversized(prompt, effective_limit):
            return prompt

        logger.warning(
            "reducing_oversized_prompt",
            original_chars=len(prompt),
            limit_chars=effective_limit,
        )

        truncation_notice = "\n\n[... Truncated due to size limit ...]"
        allowed_chars = max(10, effective_limit - len(truncation_notice))

        # Try splitting by paragraphs (\n\n)
        paragraphs = prompt.split("\n\n")
        accumulated = []
        current_len = 0

        for p in paragraphs:
            if current_len + len(p) + 2 <= allowed_chars:
                accumulated.append(p)
                current_len += len(p) + 2
            else:
                # If paragraph fits partially, split by lines
                lines = p.split("\n")
                for line in lines:
                    if current_len + len(line) + 1 <= allowed_chars:
                        accumulated.append(line)
                        current_len += len(line) + 1
                    else:
                        break
                break

        reduced = "\n\n".join(accumulated) if accumulated else prompt[:allowed_chars]
        return reduced + truncation_notice

    def chunk_prompt(self, prompt: str, chunk_size: int | None = None) -> list[str]:
        """Split a long text prompt into logical chunks of roughly `chunk_size` characters."""
        effective_size = chunk_size or self.max_input_chars

        if len(prompt) <= effective_size:
            return [prompt]

        paragraphs = prompt.split("\n\n")
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len + 2 <= effective_size:
                current_chunk.append(p)
                current_len += p_len + 2
            else:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [p]
                current_len = p_len

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [prompt[:effective_size]]
