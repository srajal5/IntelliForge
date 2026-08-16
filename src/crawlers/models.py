"""Crawler data models — separate from canonical pipeline models.

These capture raw HTTP acquisition results; later pipeline stages
transform them into Startup / Product / ResearchPaper / Job / News models.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CrawlResult(BaseModel):
    """Structured result of a single HTTP crawl attempt."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
    )

    url: str = Field(..., description="The URL that was fetched.")
    status_code: int | None = Field(
        default=None, description="HTTP status code. None on connection/timeout errors."
    )
    content: str | None = Field(
        default=None, description="Response body text. None on failure."
    )
    content_type: str | None = Field(
        default=None, description="Content-Type header value."
    )
    response_time: float = Field(
        default=0.0, ge=0.0, description="Response time in seconds."
    )
    attempts: int = Field(default=1, ge=1, description="Number of attempts made.")
    success: bool = Field(default=False, description="Whether the crawl succeeded.")
    error: str | None = Field(
        default=None, description="Error message if the crawl failed."
    )
    retry_after: float | None = Field(
        default=None, description="Retry-After header value in seconds if HTTP 429."
    )
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the crawl completed.",
    )

    @property
    def content_length(self) -> int:
        """Return byte length of the content, or 0."""
        return len(self.content.encode("utf-8")) if self.content else 0


class CrawlPolicy(BaseModel):
    """Source-specific crawling policy.

    Each source adapter can define its own policy to control
    domains, rate limits, and headers.
    """

    model_config = ConfigDict(validate_default=True)

    allowed_domains: list[str] | None = Field(
        default=None,
        description="Restrict crawling to these domains. None = unrestricted.",
    )
    request_delay: float = Field(
        default=0.0, ge=0.0, description="Delay (seconds) between requests."
    )
    concurrency: int = Field(
        default=10, ge=1, description="Max concurrent requests for this source."
    )
    headers: dict[str, str] = Field(
        default_factory=dict, description="Extra HTTP headers."
    )
    timeout: int = Field(
        default=30, ge=1, description="Request timeout in seconds."
    )
