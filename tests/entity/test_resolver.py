"""Unit tests for EntityResolver."""

import pytest
from src.entity.models import CanonicalEntity
from src.entity.repository import EntityRepository
from src.entity.resolver import EntityResolver
from src.models.enums import MatchMethod
from tests.entity.test_repository import mock_db


@pytest.fixture
def repo_with_data(mock_db):
    repo = EntityRepository(db=mock_db)
    openai = CanonicalEntity(
        canonical_id="ent_openai",
        canonical_name="OpenAI",
        aliases=["Open AI", "OpenAI Inc."],
    )
    anthropic = CanonicalEntity(
        canonical_id="ent_anthropic",
        canonical_name="Anthropic",
        aliases=["Anthropic PBC"],
    )
    repo.save_canonical_entity(openai)
    repo.save_canonical_entity(anthropic)
    return repo


def test_resolver_exact_match(repo_with_data):
    resolver = EntityResolver(repository=repo_with_data)
    mapping = resolver.resolve_entity("OpenAI")
    assert mapping.match_method == MatchMethod.EXACT
    assert mapping.canonical_id == "ent_openai"
    assert mapping.canonical_name == "OpenAI"
    assert mapping.confidence == 1.0


def test_resolver_normalized_match(repo_with_data):
    resolver = EntityResolver(repository=repo_with_data)
    mapping = resolver.resolve_entity("OpenAI, Inc.")
    assert mapping.canonical_id == "ent_openai"
    assert mapping.match_method in (MatchMethod.NORMALIZED, MatchMethod.ALIAS)


def test_resolver_alias_match(repo_with_data):
    resolver = EntityResolver(repository=repo_with_data)
    mapping = resolver.resolve_entity("Anthropic PBC")
    assert mapping.canonical_id == "ent_anthropic"
    assert mapping.match_method == MatchMethod.ALIAS


def test_resolver_idempotency(repo_with_data):
    resolver = EntityResolver(repository=repo_with_data)
    m1 = resolver.resolve_entity("OpenAI")
    m2 = resolver.resolve_entity("OpenAI")
    assert m1.canonical_id == m2.canonical_id
    assert m1.timestamp == m2.timestamp


def test_resolver_unresolved(repo_with_data):
    resolver = EntityResolver(repository=repo_with_data)
    mapping = resolver.resolve_entity("Unknown Stealth Startup")
    assert mapping.match_method == MatchMethod.UNRESOLVED
    assert mapping.confidence == 0.0
    assert "unresolved_" in mapping.canonical_id
