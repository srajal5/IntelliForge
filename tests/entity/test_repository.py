"""Unit tests for EntityRepository using mongomock or mongomock_pypipeline."""

from unittest.mock import MagicMock
import pytest
from src.entity.models import CanonicalEntity
from src.entity.repository import EntityRepository
from src.models.entity_mapping import EntityMapping


@pytest.fixture
def mock_db():
    class MockCollection:
        def __init__(self):
            self.docs = []
            self.indexes = []

        def create_index(self, keys, **kwargs):
            self.indexes.append((keys, kwargs))

        def update_one(self, filter_spec, update_spec, upsert=False):
            doc = update_spec.get("$set", {}).copy()
            add_to_set = update_spec.get("$addToSet", {})
            
            # Find existing
            existing_idx = None
            for idx, d in enumerate(self.docs):
                matched = True
                for k, v in filter_spec.items():
                    if d.get(k) != v:
                        matched = False
                        break
                if matched:
                    existing_idx = idx
                    break

            if existing_idx is not None:
                self.docs[existing_idx].update(doc)
                for k, val in add_to_set.items():
                    curr_list = self.docs[existing_idx].get(k, [])
                    if val not in curr_list:
                        curr_list.append(val)
                    self.docs[existing_idx][k] = curr_list
            elif upsert:
                new_doc = filter_spec.copy()
                new_doc.update(doc)
                for k, val in add_to_set.items():
                    new_doc[k] = [val]
                self.docs.append(new_doc)

        def find_one(self, filter_spec):
            if "$or" in filter_spec:
                for cond in filter_spec["$or"]:
                    r = self.find_one(cond)
                    if r:
                        return r
                return None
            for d in self.docs:
                matched = True
                for k, v in filter_spec.items():
                    if d.get(k) != v:
                        matched = False
                        break
                if matched:
                    return d.copy()
            return None

        def find(self, filter_spec):
            return [d.copy() for d in self.docs]

    class MockDatabase:
        def __init__(self):
            self.cols = {}

        def __getitem__(self, name):
            if name not in self.cols:
                self.cols[name] = MockCollection()
            return self.cols[name]

    return MockDatabase()


def test_repository_save_and_get_canonical(mock_db):
    repo = EntityRepository(db=mock_db)
    entity = CanonicalEntity(
        canonical_id="ent_openai_001",
        canonical_name="OpenAI",
        aliases=["Open AI"],
    )

    saved = repo.save_canonical_entity(entity)
    assert saved is True

    retrieved = repo.get_canonical_entity("ent_openai_001")
    assert retrieved is not None
    assert retrieved.canonical_name == "OpenAI"

    found_by_name = repo.find_canonical_by_name("OpenAI, Inc.")
    assert found_by_name is not None
    assert found_by_name.canonical_id == "ent_openai_001"


def test_repository_add_alias(mock_db):
    repo = EntityRepository(db=mock_db)
    entity = CanonicalEntity(
        canonical_id="ent_openai_001",
        canonical_name="OpenAI",
        aliases=["Open AI"],
    )
    repo.save_canonical_entity(entity)

    ok = repo.add_alias_to_canonical("ent_openai_001", "OpenAI Inc.")
    assert ok is True

    retrieved = repo.get_canonical_entity("ent_openai_001")
    assert "OpenAI Inc." in retrieved.aliases


def test_repository_save_and_get_mapping(mock_db):
    repo = EntityRepository(db=mock_db)
    mapping = EntityMapping(
        raw_name="OpenAi",
        normalized_name="openai",
        canonical_name="OpenAI",
        canonical_id="ent_openai_001",
        match_method="fuzzy",
        confidence=0.92,
        source_url="https://openai.com",
        timestamp="2026-08-15T12:00:00Z",
    )

    saved = repo.save_entity_mapping(mapping)
    assert saved is True

    retrieved = repo.get_mapping_by_raw_name("OpenAi")
    assert retrieved is not None
    assert retrieved.canonical_id == "ent_openai_001"
    assert retrieved.match_method.value == "fuzzy"
