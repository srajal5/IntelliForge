"""Name normalization module for Entity Resolution."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

# Suffixes that represent corporate forms
CORPORATE_SUFFIXES_REGEX = re.compile(
    r"\b(?:inc|corp|corporation|ltd|limited|llc|gmbh|pbc|co)\.?$",
    re.IGNORECASE,
)

# Non-alphanumeric punctuation to clean (preserve spaces and letters/digits)
PUNCTUATION_REGEX = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_entity_name(name: str) -> str:
    """Normalize a raw entity name string into a comparable canonical form.

    Handles:
    - Lowercase conversion
    - Unicode normalization (NFKD)
    - URL / domain stripping (e.g. "openai.com" -> "openai")
    - Punctuation removal (commas, dots, quotes, dashes)
    - Corporate suffix removal (e.g. Inc, LLC, Corp) at end of string
    - Whitespace collapsing

    Examples:
    "OpenAI, Inc." -> "openai"
    "OpenAI Inc"  -> "openai"
    "OPENAI"      -> "openai"
    "Open AI"     -> "open ai"
    "openai.com"  -> "openai"
    """
    if not name or not isinstance(name, str):
        return ""

    text = name.strip()

    # 1. Domain/URL handling
    if text.startswith("http://") or text.startswith("https://") or "github.com/" in text:
        parsed = urlparse(text)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            text = path_parts[0]
        else:
            text = parsed.netloc

    # Strip .com, .ai, .io, .org, .net if format is 'name.com' or 'name.ai'
    if re.match(r"^[a-zA-Z0-9-]+\.(?:com|ai|io|org|net|co)$", text, re.IGNORECASE):
        text = text.rsplit(".", 1)[0]

    # 2. Unicode Normalization (NFKD) & lowercase
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()

    # 3. Punctuation removal
    text = PUNCTUATION_REGEX.sub(" ", text)

    # 4. Collapse whitespace
    words = text.split()
    text = " ".join(words)

    # 5. Corporate Suffix Removal (only at the end of the normalized name)
    if text:
        text = CORPORATE_SUFFIXES_REGEX.sub("", text).strip()

    # Final whitespace cleanup
    return " ".join(text.split())
