"""Source-specific rate limiter and request delay manager."""

from __future__ import annotations

import asyncio
import time
from typing import Dict

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SourceRateLimiter:
    """Enforces per-source rate limits (max requests per minute / min request interval)."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = max(1, requests_per_minute)
        self.min_interval = 60.0 / self.requests_per_minute
        self._last_request_time: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, source: str) -> asyncio.Lock:
        if source not in self._locks:
            self._locks[source] = asyncio.Lock()
        return self._locks[source]

    async def acquire(self, source: str) -> None:
        """Wait if necessary before allowing a request for `source`."""
        lock = self._get_lock(source)
        async with lock:
            now = time.monotonic()
            last = self._last_request_time.get(source, 0.0)
            elapsed = now - last
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug("rate_limiter_delay", source=source, wait_seconds=round(wait_time, 3))
                await asyncio.sleep(wait_time)
            self._last_request_time[source] = time.monotonic()
