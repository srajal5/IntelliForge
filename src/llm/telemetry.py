"""Telemetry and usage tracking logger for LLM operations."""

from __future__ import annotations

from datetime import datetime, timezone
from src.llm.models import LLMResponse, TelemetryData, TokenUsage
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LLMTelemetryTracker:
    """Tracks performance, usage, and errors across LLM executions without logging sensitive data."""

    def __init__(self) -> None:
        self._records: list[TelemetryData] = []

    def record_execution(
        self,
        provider: str,
        model: str,
        attempts: int,
        success: bool,
        latency: float,
        input_chars: int = 0,
        output_chars: int = 0,
        usage: TokenUsage | None = None,
        error_category: str | None = None,
    ) -> TelemetryData:
        """Log structured telemetry data for an LLM call."""
        record = TelemetryData(
            provider=provider,
            model=model,
            attempts=attempts,
            success=success,
            latency=round(latency, 4),
            error_category=error_category,
            input_chars=input_chars,
            output_chars=output_chars,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._records.append(record)

        logger.info(
            "llm_telemetry_recorded",
            provider=provider,
            model=model,
            attempts=attempts,
            success=success,
            latency=round(latency, 3),
            total_tokens=usage.total_tokens if usage else None,
            error_category=error_category,
        )
        return record

    def get_records(self) -> list[TelemetryData]:
        """Return all recorded telemetry data."""
        return list(self._records)

    def clear(self) -> None:
        """Clear recorded telemetry data."""
        self._records.clear()
