"""Entity resolution service integrating Startups, Products, and Research Papers."""

from __future__ import annotations

from pymongo import MongoClient
from src.config.settings import get_settings
from src.entity.models import CanonicalEntity
from src.entity.repository import EntityRepository
from src.entity.resolver import EntityResolver
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Deterministic seed test dataset (Requirement 17)
TEST_CANONICAL_ENTITIES = [
    CanonicalEntity(
        canonical_id="ent_openai_001",
        canonical_name="OpenAI",
        entity_type="STARTUP",
        aliases=["Open AI", "OpenAI Inc.", "OpenAI, Inc.", "openai.com"],
        source_urls=["https://github.com/openai", "https://openai.com"],
    ),
    CanonicalEntity(
        canonical_id="ent_anthropic_001",
        canonical_name="Anthropic",
        entity_type="STARTUP",
        aliases=["Anthropic PBC", "anthropic.com"],
        source_urls=["https://github.com/anthropic", "https://anthropic.com"],
    ),
    CanonicalEntity(
        canonical_id="ent_deepmind_001",
        canonical_name="Google DeepMind",
        entity_type="ORGANIZATION",
        aliases=["DeepMind", "DeepMind Labs", "google deepmind"],
        source_urls=["https://deepmind.google"],
    ),
    CanonicalEntity(
        canonical_id="ent_microsoft_001",
        canonical_name="Microsoft",
        entity_type="COMPANY",
        aliases=["Microsoft Corporation", "microsoft.com"],
        source_urls=["https://github.com/microsoft", "https://microsoft.com"],
    ),
]


class EntityResolutionService:
    """Service orchestrating entity resolution across Startups, Products, Research Papers, and test datasets."""

    def __init__(
        self,
        repository: EntityRepository | None = None,
        resolver: EntityResolver | None = None,
    ) -> None:
        self.repo = repository or EntityRepository()
        self.resolver = resolver or EntityResolver(repository=self.repo)

    def seed_canonical_entities(self) -> int:
        """Seed initial canonical entities if not present in MongoDB."""
        self.repo.setup_indexes()
        count = 0
        for entity in TEST_CANONICAL_ENTITIES:
            existing = self.repo.get_canonical_entity(entity.canonical_id)
            if not existing:
                if self.repo.save_canonical_entity(entity):
                    count += 1
        return count

    def run_resolution_pipeline(self, test_names: list[str] | None = None) -> dict:
        """Run complete entity resolution pipeline across test names and database records.

        Returns summary statistics matching CLI requirement format.
        """
        self.seed_canonical_entities()

        stats = {
            "processed": 0,
            "exact": 0,
            "normalized": 0,
            "alias": 0,
            "fuzzy": 0,
            "llm": 0,
            "unresolved": 0,
            "canonical_entities": 0,
            "mappings_created": 0,
        }

        names_to_process: list[tuple[str, str | None, str]] = []

        # 1. Add provided test dataset or default test dataset (Requirement 17)
        default_test_set = [
            "OpenAI",
            "Open AI",
            "OpenAI Inc.",
            "OpenAI, Inc.",
            "openai.com",
            "Anthropic",
            "Anthropic PBC",
            "Google DeepMind",
            "DeepMind",
            "DeepMind Labs",
            "Microsoft",
            "Microsoft Corporation",
            "Acme AI Labs",
            "Acme Artificial Intelligence",
            "Supabase",
            "Supabase Inc",
            "Hugging Face",
            "HuggingFace",
            "Unknown AI Research",
            "Random Ambiguous Entity Inc",
        ]

        raw_names = test_names or default_test_set
        for n in raw_names:
            names_to_process.append((n, None, "TEST"))

        # 2. Add Startups, Products, Research Papers from DB
        settings = get_settings()
        client = MongoClient(settings.mongodb_uri)
        db = client[settings.mongodb_database]

        startups = list(db["startups"].find({}))
        for s in startups:
            entity_name = s.get("content", {}).get("entityName")
            url = s.get("source", {}).get("url")
            if entity_name:
                names_to_process.append((entity_name, url, "STARTUP"))

        products = list(db["products"].find({}))
        for p in products:
            startup_name = p.get("content", {}).get("startupName")
            url = p.get("source", {}).get("url")
            if startup_name:
                names_to_process.append((startup_name, url, "PRODUCT"))

        # 3. Process names through Resolver
        for raw_name, url, record_type in names_to_process:
            mapping = self.resolver.resolve_entity(raw_name=raw_name, source_url=url, entity_type=record_type)
            stats["processed"] += 1

            method_val = mapping.match_method.value.lower()
            if method_val in stats:
                stats[method_val] += 1
            else:
                stats["unresolved"] += 1

        # 4. Attach resolved canonical metadata to Startup and Product documents in DB
        for s in startups:
            doc_id = s["_id"]
            entity_name = s.get("content", {}).get("entityName")
            if entity_name:
                m = self.repo.get_mapping_by_raw_name(entity_name)
                if m and m.canonical_id:
                    db["startups"].update_one(
                        {"_id": doc_id},
                        {
                            "$set": {
                                "canonical_entity_id": m.canonical_id,
                                "canonical_name": m.canonical_name,
                                "resolution_match_method": m.match_method.value,
                            }
                        },
                    )

        for p in products:
            doc_id = p["_id"]
            startup_name = p.get("content", {}).get("startupName")
            if startup_name:
                m = self.repo.get_mapping_by_raw_name(startup_name)
                if m and m.canonical_id:
                    db["products"].update_one(
                        {"_id": doc_id},
                        {
                            "$set": {
                                "canonical_startup_id": m.canonical_id,
                                "canonical_startup_name": m.canonical_name,
                                "resolution_match_method": m.match_method.value,
                            }
                        },
                    )

        client.close()

        all_canonicals = self.repo.get_all_canonical_entities()
        all_mappings = self.repo.get_all_entity_mappings()

        stats["canonical_entities"] = len(all_canonicals)
        stats["mappings_created"] = len(all_mappings)

        logger.info("entity_resolution_pipeline_completed", **stats)
        return stats
