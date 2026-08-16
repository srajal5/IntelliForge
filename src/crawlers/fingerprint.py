"""URL fingerprinting for deduplication.

Normalises URLs and produces deterministic SHA-256 fingerprints
so that the same logical resource always maps to the same key.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Normalise a URL for consistent comparison.

    * Lowercases scheme and host.
    * Strips trailing slashes from path.
    * Sorts query parameters alphabetically.
    * Drops fragment.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    params = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(params.items()), doseq=True)
    return urlunparse((scheme, netloc, path, "", sorted_query, ""))


def url_fingerprint(url: str) -> str:
    """Return a SHA-256 hex digest of the normalised URL."""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
