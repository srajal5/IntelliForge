"""Integration test verifying EntityResolutionService and requirement 17 canonical groupings."""

import pytest
from src.entity.repository import EntityRepository
from src.entity.resolver import EntityResolver
from src.services.entity_resolution import EntityResolutionService
from src.models.enums import MatchMethod
from tests.entity.test_repository import mock_db


def test_entity_resolution_service_test_dataset(mock_db):
    repo = EntityRepository(db=mock_db)
    svc = EntityResolutionService(repository=repo)
    svc.seed_canonical_entities()

    test_names = [
        "OpenAI",
        "Open AI",
        "OpenAI Inc.",
        "OpenAI, Inc.",
        "Anthropic",
        "Anthropic PBC",
        "Google DeepMind",
        "DeepMind",
        "Microsoft",
        "Microsoft Corporation",
    ]

    res = svc.run_resolution_pipeline(test_names=test_names)
    assert res["processed"] >= 10
    assert res["canonical_entities"] >= 4
    assert res["mappings_created"] >= 10

    # Verify grouping correctness
    m_openai1 = repo.get_mapping_by_raw_name("OpenAI")
    m_openai2 = repo.get_mapping_by_raw_name("Open AI")
    m_openai3 = repo.get_mapping_by_raw_name("OpenAI Inc.")
    m_openai4 = repo.get_mapping_by_raw_name("OpenAI, Inc.")

    assert m_openai1.canonical_id == "ent_openai_001"
    assert m_openai2.canonical_id == "ent_openai_001"
    assert m_openai3.canonical_id == "ent_openai_001"
    assert m_openai4.canonical_id == "ent_openai_001"

    m_anth1 = repo.get_mapping_by_raw_name("Anthropic")
    m_anth2 = repo.get_mapping_by_raw_name("Anthropic PBC")
    assert m_anth1.canonical_id == "ent_anthropic_001"
    assert m_anth2.canonical_id == "ent_anthropic_001"

    m_dm1 = repo.get_mapping_by_raw_name("Google DeepMind")
    m_dm2 = repo.get_mapping_by_raw_name("DeepMind")
    assert m_dm1.canonical_id == "ent_deepmind_001"
    assert m_dm2.canonical_id == "ent_deepmind_001"

    m_ms1 = repo.get_mapping_by_raw_name("Microsoft")
    m_ms2 = repo.get_mapping_by_raw_name("Microsoft Corporation")
    assert m_ms1.canonical_id == "ent_microsoft_001"
    assert m_ms2.canonical_id == "ent_microsoft_001"
