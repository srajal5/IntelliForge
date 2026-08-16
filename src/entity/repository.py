"""MongoDB repository for Canonical Entities and Entity Mappings."""

from __future__ import annotations

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from src.config.settings import get_settings
from src.entity.models import CanonicalEntity
from src.entity.normalizer import normalize_entity_name
from src.models.entity_mapping import EntityMapping
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EntityRepository:
    """MongoDB repository managing canonical_entities and entity_mappings collections."""

    CANONICAL_COLLECTION = "canonical_entities"
    MAPPINGS_COLLECTION = "entity_mappings"

    def __init__(self, db: Database | None = None) -> None:
        self._db = db

    def _get_db(self) -> Database:
        if self._db is None:
            settings = get_settings()
            client = MongoClient(settings.mongodb_uri)
            self._db = client[settings.mongodb_database]
        return self._db

    def setup_indexes(self) -> None:
        """Create required indexes for canonical_entities and entity_mappings collections."""
        try:
            db = self._get_db()
            can_col = db[self.CANONICAL_COLLECTION]
            can_col.create_index([("canonical_id", ASCENDING)], unique=True)
            can_col.create_index([("normalized_name", ASCENDING)], unique=True)
            can_col.create_index([("aliases", ASCENDING)])

            map_col = db[self.MAPPINGS_COLLECTION]
            map_col.create_index([("raw_name", ASCENDING)], unique=True)
            map_col.create_index([("canonical_id", ASCENDING)])
            logger.info("entity_repository_indexes_created")
        except PyMongoError as exc:
            logger.error("entity_repository_index_creation_failed", error=str(exc))

    def save_canonical_entity(self, entity: CanonicalEntity) -> bool:
        """Save a CanonicalEntity to MongoDB.

        Returns True if inserted/updated, False on failure or duplicate.
        """
        try:
            db = self._get_db()
            col = db[self.CANONICAL_COLLECTION]
            doc = entity.to_dict()
            doc["normalized_name"] = normalize_entity_name(entity.canonical_name)

            col.update_one(
                {"canonical_id": entity.canonical_id},
                {"$set": doc},
                upsert=True,
            )
            return True
        except PyMongoError as exc:
            logger.error("save_canonical_entity_failed", canonical_id=entity.canonical_id, error=str(exc))
            return False

    def get_canonical_entity(self, canonical_id: str) -> CanonicalEntity | None:
        """Fetch a CanonicalEntity by canonical_id."""
        try:
            db = self._get_db()
            col = db[self.CANONICAL_COLLECTION]
            doc = col.find_one({"canonical_id": canonical_id})
            if not doc:
                return None
            doc.pop("_id", None)
            doc.pop("normalized_name", None)
            return CanonicalEntity(**doc)
        except Exception as exc:
            logger.error("get_canonical_entity_failed", canonical_id=canonical_id, error=str(exc))
            return None

    def get_all_canonical_entities(self) -> list[CanonicalEntity]:
        """Fetch all canonical entities from MongoDB."""
        try:
            db = self._get_db()
            col = db[self.CANONICAL_COLLECTION]
            docs = list(col.find({}))
            entities: list[CanonicalEntity] = []
            for doc in docs:
                doc.pop("_id", None)
                doc.pop("normalized_name", None)
                entities.append(CanonicalEntity(**doc))
            return entities
        except Exception as exc:
            logger.error("get_all_canonical_entities_failed", error=str(exc))
            return []

    def find_canonical_by_name(self, name: str) -> CanonicalEntity | None:
        """Find a canonical entity by its display name or normalized name."""
        try:
            db = self._get_db()
            col = db[self.CANONICAL_COLLECTION]
            norm = normalize_entity_name(name)
            doc = col.find_one({"$or": [{"canonical_name": name}, {"normalized_name": norm}]})
            if not doc:
                return None
            doc.pop("_id", None)
            doc.pop("normalized_name", None)
            return CanonicalEntity(**doc)
        except Exception as exc:
            logger.error("find_canonical_by_name_failed", name=name, error=str(exc))
            return None

    def add_alias_to_canonical(self, canonical_id: str, alias: str) -> bool:
        """Add a new alias string to an existing canonical entity."""
        if not alias or not alias.strip():
            return False
        try:
            db = self._get_db()
            col = db[self.CANONICAL_COLLECTION]
            col.update_one(
                {"canonical_id": canonical_id},
                {"$addToSet": {"aliases": alias.strip()}},
            )
            return True
        except PyMongoError as exc:
            logger.error("add_alias_to_canonical_failed", canonical_id=canonical_id, alias=alias, error=str(exc))
            return False

    def save_entity_mapping(self, mapping: EntityMapping) -> bool:
        """Save an EntityMapping to MongoDB `entity_mappings` collection."""
        try:
            db = self._get_db()
            col = db[self.MAPPINGS_COLLECTION]
            doc = mapping.to_dict()
            col.update_one(
                {"raw_name": mapping.raw_name},
                {"$set": doc},
                upsert=True,
            )
            return True
        except PyMongoError as exc:
            logger.error("save_entity_mapping_failed", raw_name=mapping.raw_name, error=str(exc))
            return False

    def get_mapping_by_raw_name(self, raw_name: str) -> EntityMapping | None:
        """Retrieve an EntityMapping by raw entity name."""
        try:
            db = self._get_db()
            col = db[self.MAPPINGS_COLLECTION]
            doc = col.find_one({"raw_name": raw_name})
            if not doc:
                return None
            doc.pop("_id", None)
            return EntityMapping(**doc)
        except Exception as exc:
            logger.error("get_mapping_by_raw_name_failed", raw_name=raw_name, error=str(exc))
            return None

    def get_all_entity_mappings(self) -> list[EntityMapping]:
        """Fetch all entity mappings from MongoDB."""
        try:
            db = self._get_db()
            col = db[self.MAPPINGS_COLLECTION]
            docs = list(col.find({}))
            mappings: list[EntityMapping] = []
            for doc in docs:
                doc.pop("_id", None)
                mappings.append(EntityMapping(**doc))
            return mappings
        except Exception as exc:
            logger.error("get_all_entity_mappings_failed", error=str(exc))
            return []
