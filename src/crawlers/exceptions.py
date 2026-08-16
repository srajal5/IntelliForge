"""Crawler-specific exceptions."""


class CrawlerError(Exception):
    """Base exception for all crawler errors."""


class CrawlerTimeoutError(CrawlerError):
    """Request timed out."""


class CrawlerConnectionError(CrawlerError):
    """Could not connect to the target host."""


class CrawlerHttpError(CrawlerError):
    """HTTP response indicated an error."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class CrawlerRateLimitError(CrawlerHttpError):
    """Server returned 429 Too Many Requests."""

    def __init__(self, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(429, "Rate limited")


class CrawlerRetryExhaustedError(CrawlerError):
    """All retry attempts have been exhausted."""

    def __init__(self, url: str, attempts: int, last_error: str = ""):
        self.url = url
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Retry exhausted for {url} after {attempts} attempts: {last_error}"
        )
