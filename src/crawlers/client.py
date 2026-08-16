"""Async HTTP client — production aiohttp implementation of BaseCrawler.

Features
--------
* Connection pooling via ``aiohttp.TCPConnector``
* Bounded concurrency via ``asyncio.Semaphore``
* Exponential backoff with jitter on transient failures
* Per-request delay for polite crawling
* Structured logging (no secrets)
* Clean session lifecycle (async context manager)
* Cache hook integration
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import aiohttp

from src.crawlers.base import BaseCrawler
from src.crawlers.cache import CrawlCache, NullCache
from src.crawlers.exceptions import (
    CrawlerConnectionError,
    CrawlerRetryExhaustedError,
    CrawlerTimeoutError,
)
from src.crawlers.fingerprint import url_fingerprint
from src.crawlers.models import CrawlPolicy, CrawlResult
from src.crawlers.retry import compute_backoff, is_permanent_error, is_retryable_status
from src.utils.logging import get_logger

logger = get_logger("crawlers.client")

# Default user-agent for polite identification.
_DEFAULT_UA = (
    "AIIntelligencePipeline/1.0 "
    "(+https://github.com/ai-intelligence-pipeline; research)"
)


class AsyncHttpClient(BaseCrawler):
    """aiohttp-backed async crawler with retry, concurrency, and caching.

    Parameters
    ----------
    concurrency:
        Maximum number of simultaneous in-flight HTTP requests.
    timeout:
        Per-request timeout in seconds.
    max_retries:
        Maximum attempts per URL (including the first).
    backoff_base:
        Base of the exponential backoff.
    backoff_max:
        Ceiling for the backoff delay in seconds.
    user_agent:
        User-Agent header string.
    policy:
        Optional source-specific crawl policy (overrides defaults).
    cache:
        Optional CrawlCache implementation. Defaults to NullCache.
    """

    def __init__(
        self,
        *,
        concurrency: int = 10,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        backoff_max: float = 60.0,
        user_agent: str = _DEFAULT_UA,
        policy: CrawlPolicy | None = None,
        cache: CrawlCache | None = None,
    ) -> None:
        self._concurrency = policy.concurrency if policy else concurrency
        self._timeout = policy.timeout if policy else timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._user_agent = user_agent
        self._request_delay = policy.request_delay if policy else 0.0
        self._extra_headers: dict[str, str] = policy.headers if policy else {}

        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._cache: CrawlCache = cache or NullCache()
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazily create and return a reusable ClientSession."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self._concurrency,
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            headers = {"User-Agent": self._user_agent, **self._extra_headers}
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers,
            )
        return self._session

    async def close(self) -> None:
        """Gracefully close the underlying session and connector."""
        if self._session and not self._session.closed:
            await self._session.close()
            # Allow the event loop to close underlying connections.
            await asyncio.sleep(0.1)
        self._session = None
        logger.info("session_closed")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(self, url: str) -> CrawlResult:
        """Fetch a single URL with retry and caching."""
        # --- cache lookup ---
        fp = url_fingerprint(url)
        cached = await self._cache.get(fp)
        if cached is not None:
            logger.debug("cache_hit", url=url)
            return cached

        # --- fetch with retries ---
        result: CrawlResult | None = None
        for attempt in range(1, self._max_retries + 1):
            result = await self._fetch_once(url, attempt)

            if result.success:
                await self._cache.set(fp, result)
                return result

            if is_permanent_error(result.status_code):
                logger.warning(
                    "crawl_permanent_error",
                    url=url,
                    status=result.status_code,
                    attempt=attempt,
                )
                return result

            if not is_retryable_status(result.status_code):
                return result

            # --- retryable failure → back off ---
            if attempt < self._max_retries:
                delay = compute_backoff(
                    attempt,
                    backoff_base=self._backoff_base,
                    backoff_max=self._backoff_max,
                )
                if result.retry_after is not None:
                    delay = max(delay, result.retry_after)

                logger.info(
                    "crawl_retry",
                    url=url,
                    status=result.status_code,
                    attempt=attempt,
                    delay=delay,
                    error=result.error,
                )
                await asyncio.sleep(delay)

        # All retries exhausted.
        assert result is not None
        logger.error(
            "crawl_failed",
            url=url,
            attempts=self._max_retries,
            last_status=result.status_code,
            error=result.error,
        )
        return result

    async def fetch_many(self, urls: list[str]) -> list[CrawlResult]:
        """Fetch multiple URLs concurrently with bounded parallelism.

        Individual failures are captured in their CrawlResult —
        a single bad URL never crashes the batch.
        """
        tasks = [self.fetch(url) for url in urls]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _fetch_once(self, url: str, attempt: int) -> CrawlResult:
        """Execute a single HTTP GET behind the concurrency semaphore."""
        start = time.monotonic()
        session = await self._get_session()

        try:
            async with self._semaphore:
                async with session.get(url, allow_redirects=True) as resp:
                    elapsed = round(time.monotonic() - start, 4)
                    body = await resp.text()

                    if resp.status < 400:
                        logger.info(
                            "crawl_success",
                            url=url,
                            status=resp.status,
                            attempt=attempt,
                            response_time=elapsed,
                        )
                        return CrawlResult(
                            url=url,
                            status_code=resp.status,
                            content=body,
                            content_type=resp.content_type,
                            response_time=elapsed,
                            attempts=attempt,
                            success=True,
                        )

                    # Non-success HTTP status.
                    retry_after_val: float | None = None
                    if resp.status == 429:
                        header_val = resp.headers.get("Retry-After")
                        if header_val:
                            try:
                                retry_after_val = float(header_val)
                            except ValueError:
                                retry_after_val = 5.0

                    return CrawlResult(
                        url=url,
                        status_code=resp.status,
                        content=body,
                        content_type=resp.content_type,
                        response_time=elapsed,
                        attempts=attempt,
                        success=False,
                        error=f"HTTP {resp.status}",
                        retry_after=retry_after_val,
                    )

        except asyncio.TimeoutError:
            elapsed = round(time.monotonic() - start, 4)
            return CrawlResult(
                url=url,
                status_code=None,
                response_time=elapsed,
                attempts=attempt,
                success=False,
                error="Timeout",
            )
        except aiohttp.ClientConnectorError as exc:
            elapsed = round(time.monotonic() - start, 4)
            return CrawlResult(
                url=url,
                status_code=None,
                response_time=elapsed,
                attempts=attempt,
                success=False,
                error=f"Connection error: {exc}",
            )
        except aiohttp.ClientError as exc:
            elapsed = round(time.monotonic() - start, 4)
            return CrawlResult(
                url=url,
                status_code=None,
                response_time=elapsed,
                attempts=attempt,
                success=False,
                error=str(exc),
            )
        finally:
            if self._request_delay > 0:
                await asyncio.sleep(self._request_delay)

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings) -> AsyncHttpClient:
        """Create a client from the application Settings object."""
        extra_headers: dict[str, str] = {}
        if getattr(settings, "github_token", None):
            extra_headers["Authorization"] = f"token {settings.github_token}"
        policy = CrawlPolicy(headers=extra_headers) if extra_headers else None

        return cls(
            concurrency=settings.crawler_concurrency,
            timeout=settings.crawler_timeout,
            max_retries=settings.crawler_max_retries,
            backoff_base=settings.crawler_backoff_base,
            backoff_max=settings.crawler_backoff_max,
            user_agent=settings.crawler_user_agent,
            policy=policy,
        )
