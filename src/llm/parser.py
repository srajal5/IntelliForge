"""Parser and validator for extracting structured Pydantic objects from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar
from pydantic import BaseModel, ValidationError

from src.llm.exceptions import StructuredOutputError
from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class JSONParser:
    """Utility for extracting and validating JSON structures from raw LLM text outputs."""

    @staticmethod
    def extract_json_string(text: str) -> str:
        """Extract JSON string from raw text, code fences, or text blocks."""
        if not text or not text.strip():
            raise StructuredOutputError("Raw text response is empty", raw_text=text)

        cleaned = text.strip()

        # 1. Check for markdown code fences ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL | re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()

        # 2. Check for object block {...} or array block [...]
        obj_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if obj_match:
            return obj_match.group(1).strip()

        return cleaned

    @classmethod
    def parse_json_dict(cls, text: str) -> dict[str, Any]:
        """Parse raw text into a Python dictionary."""
        json_str = cls.extract_json_string(text)
        try:
            val = json.loads(json_str)
            if isinstance(val, dict):
                return val
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                return val[0]
            raise StructuredOutputError(f"Parsed JSON is not a dictionary: {type(val)}", raw_text=text)
        except json.JSONDecodeError as exc:
            logger.warning("json_decode_failed", error=str(exc), raw_snippet=text[:200])
            raise StructuredOutputError(f"JSON decode failed: {exc}", raw_text=text) from exc

    @classmethod
    def extract_structured(
        cls,
        text: str,
        target_schema: type[T],
        context: dict[str, Any] | None = None,
    ) -> T:
        """Extract JSON from raw LLM output text and validate against a target Pydantic schema."""
        json_data = cls.parse_json_dict(text)
        try:
            return target_schema(**json_data)
        except ValidationError as exc:
            logger.warning(
                "pydantic_validation_failed",
                target_schema=target_schema.__name__,
                errors=exc.errors(include_url=False),
            )
            raise StructuredOutputError(
                f"Validation against {target_schema.__name__} failed: {exc}",
                raw_text=text,
            ) from exc
