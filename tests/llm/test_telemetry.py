"""Unit tests for telemetry logging and token metrics tracking."""

from src.llm.telemetry import LLMTelemetryTracker
from src.llm.models import TokenUsage


def test_telemetry_tracker_record_and_get():
    tracker = LLMTelemetryTracker()

    usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    record = tracker.record_execution(
        provider="gemini",
        model="gemini-1.5-flash",
        attempts=1,
        success=True,
        latency=0.45,
        input_chars=500,
        output_chars=200,
        usage=usage,
    )

    assert record.provider == "gemini"
    assert record.total_tokens == 150
    assert len(tracker.get_records()) == 1

    tracker.clear()
    assert len(tracker.get_records()) == 0
