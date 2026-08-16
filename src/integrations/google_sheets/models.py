"""Google Sheets integration models and options."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExportOptions:
    """Options governing Google Sheets export operations."""

    spreadsheet_id: str = ""
    service_account_json: str = ""
    service_account_file: str = ""
    batch_size: int = 500
    dry_run: bool = False
    vertical: str | None = None  # None means all 5 verticals


@dataclass
class VerticalTelemetry:
    """Telemetry for a single vertical export run."""

    vertical: str
    queried: int = 0
    valid: int = 0
    invalid: int = 0
    skipped: int = 0
    written: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "vertical": self.vertical,
            "queried": self.queried,
            "valid": self.valid,
            "invalid": self.invalid,
            "skipped": self.skipped,
            "written": self.written,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


@dataclass
class ExportSummary:
    """Overall summary of Google Sheets export run across verticals."""

    status: str  # "success", "error", "not_configured", "dry_run"
    spreadsheet_id: str = ""
    verticals: dict[str, VerticalTelemetry] = field(default_factory=dict)
    total_written: int = 0
    total_elapsed_seconds: float = 0.0
    error: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "status": self.status,
            "spreadsheet_id": self.spreadsheet_id,
            "total_written": self.total_written,
            "total_elapsed_seconds": round(self.total_elapsed_seconds, 3),
        }
        if self.message:
            res["message"] = self.message
        if self.error:
            res["error"] = self.error
        for k, v in self.verticals.items():
            res[k] = v.to_dict()
        return res
