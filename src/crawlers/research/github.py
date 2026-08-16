"""GitHub repository discovery and star count retrieval for research papers."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from src.crawlers.client import AsyncHttpClient
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Regex for matching GitHub repository URLs
GITHUB_REPO_REGEX = re.compile(
    r"https?://github\.com/([a-zA-Z0-9\-_]+)/([a-zA-Z0-9\._\-]+)",
    re.IGNORECASE,
)

# Paths/words that indicate a non-repository GitHub page
NON_REPO_PATHS = {
    "sponsors",
    "settings",
    "features",
    "topics",
    "collections",
    "trending",
    "events",
    "marketplace",
    "pricing",
    "orgs",
    "users",
    "about",
}


class GitHubDiscoverer:
    """Extracts and validates GitHub repository URLs from paper abstracts/texts."""

    @classmethod
    def discover_github_url(cls, text: str) -> str | None:
        """Find the first legitimate GitHub repository URL in text."""
        if not text:
            return None

        for match in GITHUB_REPO_REGEX.finditer(text):
            owner, repo = match.group(1), match.group(2)

            # Strip trailing punctuation or extension
            repo = re.sub(r"[\.,;:!)]+$", "", repo)
            if repo.endswith(".git"):
                repo = repo[:-4]

            # Ignore reserved GitHub paths
            if owner.lower() in NON_REPO_PATHS or repo.lower() in NON_REPO_PATHS:
                continue

            # Basic sanity checks for owner/repo length
            if len(owner) < 1 or len(repo) < 1:
                continue

            clean_url = f"https://github.com/{owner}/{repo}"
            logger.info("github_url_discovered", url=clean_url)
            return clean_url

        return None


class GitHubMetadataFetcher:
    """Retrieves metadata (star count) for validated GitHub repositories via GitHub REST API."""

    def __init__(self, client: AsyncHttpClient | None = None, token: str | None = None) -> None:
        self.client = client
        self.token = token

    async def fetch_stars(self, github_url: str) -> tuple[str | None, int | None]:
        """Fetch stargazers count for a given GitHub repository URL.

        Returns:
            (github_url, stars):
            - If repo is 404 (does not exist): returns (None, None).
            - If repo exists & stars retrieved: returns (github_url, stars).
            - If repo exists but star retrieval fails (rate limit/network): returns (github_url, None).
        """
        if not github_url:
            return None, None

        parsed = urlparse(github_url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            return None, None

        owner, repo = parts[0], parts[1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        # If no client was injected, create a temporary AsyncHttpClient
        own_client = False
        if self.client is None:
            self.client = AsyncHttpClient(concurrency=3, timeout=10, max_retries=1)
            own_client = True

        try:
            result = await self.client.fetch(api_url)

            if not result.success:
                if result.status_code == 404:
                    logger.warning("github_repo_not_found", url=github_url)
                    return None, None
                logger.warning(
                    "github_api_failed",
                    url=github_url,
                    status=result.status_code,
                    error=result.error,
                )
                return github_url, None

            # Parse JSON payload
            import json
            data = json.loads(result.content)
            stars = data.get("stargazers_count")
            if isinstance(stars, int) and stars >= 0:
                logger.info("github_stars_retrieved", url=github_url, stars=stars)
                return github_url, stars

            return github_url, None

        except Exception as exc:
            logger.warning("github_stars_fetch_exception", url=github_url, error=str(exc))
            return github_url, None

        finally:
            if own_client and self.client:
                await self.client.close()
