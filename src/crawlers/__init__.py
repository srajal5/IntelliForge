"""Async crawler engine for the AI Intelligence Pipeline.

Public API
----------
* ``AsyncHttpClient``  – aiohttp-backed crawler with retry & pooling.
* ``BaseCrawler``      – abstract interface for backend swapping.
* ``CrawlResult``      – structured fetch result.
* ``CrawlPolicy``      – source-specific crawl configuration.
* ``CrawlCache`` / ``NullCache`` – cache hook (Redis later).
* ``url_fingerprint``  – deterministic URL hashing.
"""

from src.crawlers.base import BaseCrawler
from src.crawlers.cache import CrawlCache, NullCache
from src.crawlers.client import AsyncHttpClient
from src.crawlers.exceptions import (
    CrawlerConnectionError,
    CrawlerError,
    CrawlerHttpError,
    CrawlerRateLimitError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
)
from src.crawlers.fingerprint import normalize_url, url_fingerprint
from src.crawlers.models import CrawlPolicy, CrawlResult
from src.crawlers.retry import (
    RETRYABLE_STATUS_CODES,
    compute_backoff,
    is_permanent_error,
    is_retryable_status,
)

__all__ = [
    # Core
    "AsyncHttpClient",
    "BaseCrawler",
    "CrawlResult",
    "CrawlPolicy",
    # Cache
    "CrawlCache",
    "NullCache",
    # Fingerprint
    "normalize_url",
    "url_fingerprint",
    # Retry
    "compute_backoff",
    "is_retryable_status",
    "is_permanent_error",
    "RETRYABLE_STATUS_CODES",
    # Exceptions
    "CrawlerError",
    "CrawlerTimeoutError",
    "CrawlerConnectionError",
    "CrawlerHttpError",
    "CrawlerRateLimitError",
    "CrawlerRetryExhaustedError",
]
