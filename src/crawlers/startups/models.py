"""Data models for raw startup crawler payloads."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawStartup:
    """Raw startup payload object extracted by StartupParser."""

    entity_name: str
    source_url: str
    source_name: str = "GitHub Organizations"
    employee_count: int | None = None
    description: str | None = None
    is_qualified: bool = True
    qualification_category: str = "STARTUP_COMPANY"
    qualification_reasons: list[str] = field(default_factory=list)
