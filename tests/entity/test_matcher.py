"""Unit tests for entity matcher."""

import pytest
from src.entity.fallback_interface import LLMFallbackCandidate, LLMFallbackResult, MockEntityLLMFallback
from src.entity.matcher import EntityMatcher, MatchResult
from src.entity.models import CanonicalEntity
from src.models.enums import MatchMethod


@pytest.fixture
def sample_candidates() -> list[CanonicalEntity]:
    return [
        CanonicalEntity(
            canonical_id="ent_openai",
            canonical_name="OpenAI",
            aliases=["Open AI", "OpenAI Inc."],
            source_urls=["https://openai.com"],
        ),
        CanonicalEntity(
            canonical_id="ent_anthropic",
            canonical_name="Anthropic",
            aliases=["Anthropic PBC"],
            source_urls=["https://anthropic.com"],
        ),
        CanonicalEntity(
            canonical_id="ent_deepmind",
            canonical_name="Google DeepMind",
            aliases=["DeepMind"],
            source_urls=["https://deepmind.google"],
        ),
    ]


def test_exact_match(sample_candidates):
    matcher = EntityMatcher()
    res = matcher.match("OpenAI", sample_candidates)
    assert res.match_method == MatchMethod.EXACT
    assert res.canonical_id == "ent_openai"
    assert res.confidence == 1.0


def test_normalized_match(sample_candidates):
    matcher = EntityMatcher()
    res = matcher.match("OPENAI", sample_candidates)
    # "OPENAI" normalizes to "openai", matching "OpenAI" normalized
    assert res.match_method in (MatchMethod.EXACT, MatchMethod.NORMALIZED)
    assert res.canonical_id == "ent_openai"


def test_alias_match(sample_candidates):
    matcher = EntityMatcher()
    res = matcher.match("OpenAI Inc.", sample_candidates)
    assert res.match_method == MatchMethod.ALIAS
    assert res.canonical_id == "ent_openai"
    assert res.confidence == 0.90


def test_fuzzy_match(sample_candidates):
    matcher = EntityMatcher()
    res = matcher.match("DeepMind", sample_candidates)
    # "DeepMind" matches alias "DeepMind" -> ALIAS or FUZZY
    assert res.canonical_id == "ent_deepmind"


def test_ambiguity_triggers_unresolved_without_llm():
    matcher = EntityMatcher(ambiguity_delta=0.10)
    candidates = [
        CanonicalEntity(canonical_id="ent_acme_1", canonical_name="Acme AI Labs"),
        CanonicalEntity(canonical_id="ent_acme_2", canonical_name="Acme AI Research"),
    ]
    res = matcher.match("Acme AI", candidates)
    assert res.match_method == MatchMethod.UNRESOLVED
    assert res.canonical_id is None


def test_ambiguity_triggers_llm_fallback(sample_candidates):
    mock_llm = MockEntityLLMFallback(
        default_response=LLMFallbackResult(
            selected_canonical_id="ent_acme_1",
            canonical_name="Acme AI Labs",
            confidence=0.85,
            reason="LLM selected Acme AI Labs based on context",
        )
    )
    matcher = EntityMatcher(ambiguity_delta=0.10, llm_fallback=mock_llm)
    candidates = [
        CanonicalEntity(canonical_id="ent_acme_1", canonical_name="Acme AI Labs"),
        CanonicalEntity(canonical_id="ent_acme_2", canonical_name="Acme AI Research"),
    ]
    res = matcher.match("Acme AI", candidates)
    assert res.match_method == MatchMethod.LLM
    assert res.canonical_id == "ent_acme_1"
    assert res.confidence == 0.85


def test_unresolved_low_score(sample_candidates):
    matcher = EntityMatcher()
    res = matcher.match("Random Totally Unknown Entity", sample_candidates)
    assert res.match_method == MatchMethod.UNRESOLVED
    assert res.canonical_id is None
    assert res.confidence == 0.0
