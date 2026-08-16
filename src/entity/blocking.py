"""Candidate blocking utilities for optimizing entity resolution matching performance."""

from __future__ import annotations

from typing import Iterable, Set

from src.entity.models import CanonicalEntity
from src.entity.normalizer import normalize_entity_name


def generate_blocking_keys(name: str) -> Set[str]:
    """Generate blocking keys (prefix, first token, length band) for a given entity name."""
    keys: Set[str] = set()
    norm = normalize_entity_name(name)
    if not norm:
        return keys

    # Key 1: 3-character prefix
    if len(norm) >= 3:
        keys.add(f"pref:{norm[:3]}")

    # Key 2: First token
    tokens = norm.split()
    if tokens:
        keys.add(f"tok:{tokens[0]}")

    # Key 3: Token count band
    keys.add(f"len:{len(tokens)}")

    return keys


def filter_candidates_with_blocking(
    raw_name: str,
    candidates: Iterable[CanonicalEntity],
) -> list[CanonicalEntity]:
    """Filter canonical entity candidates using blocking keys before expensive fuzzy matching."""
    raw_keys = generate_blocking_keys(raw_name)
    if not raw_keys:
        return list(candidates)

    filtered: list[CanonicalEntity] = []

    for entity in candidates:
        # Check canonical name blocking keys
        entity_keys = generate_blocking_keys(entity.canonical_name)
        # Check alias blocking keys
        for alias in entity.aliases:
            entity_keys.update(generate_blocking_keys(alias))

        # If any key matches, keep candidate
        if raw_keys & entity_keys:
            filtered.append(entity)

    # Fallback to all candidates if blocking eliminates everything
    return filtered if filtered else list(candidates)
