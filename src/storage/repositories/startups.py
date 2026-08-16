"""MongoDB repository for storing and deduplicating Startup canonical records."""

from __future__ import annotations

from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

from src.config.settings import Settings, get_settings
from src.crawlers.fingerprint import normalize_url, url_fingerprint
from src.models.startup import Startup
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StartupRepository:
    """Handles persistence, unique indexing, and deduplication for Startup records in MongoDB."""

    COLLECTION_NAME = "startups"

    def __init__(self, settings: Settings | None = None, client: MongoClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._db = None

    def _get_db(self):
        if self._db is None:
            if self._client is None:
                self._client = MongoClient(
                    self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
                )
            self._db = self._client[self.settings.mongodb_database]
        return self._db

    def setup_indexes(self) -> None:
        """Create unique index on source.url and url_fingerprint for deduplication."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            col.create_index([("source.url", ASCENDING)], unique=True, sparse=True)
            col.create_index([("url_fingerprint", ASCENDING)], unique=True, sparse=True)
            col.create_index([("content.entityName", ASCENDING)], sparse=True)
            logger.info("startup_repository_indexes_setup")
        except Exception as exc:
            logger.warning("startup_repository_indexes_failed", error=str(exc))

    def exists(self, source_url: str, entity_name: str | None = None) -> bool:
        """Check if a startup already exists in MongoDB by source URL or fingerprint."""
        if not source_url:
            return False
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            norm_url = normalize_url(source_url)
            fp = url_fingerprint(source_url)

            or_clauses: list[dict] = [
                {"source.url": norm_url},
                {"source.url": source_url},
                {"url_fingerprint": fp},
            ]
            if entity_name:
                or_clauses.append({"content.entityName": entity_name})

            query = {"$or": or_clauses}
            return col.count_documents(query, limit=1) > 0
        except Exception as exc:
            logger.error("startup_repository_exists_check_failed", url=source_url, error=str(exc))
            return False

    def save(self, startup: Startup, provenance: dict | None = None) -> bool:
        """Save a validated Startup record into MongoDB.

        Returns True if inserted, False if duplicate.
        """
        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        startup_dict = startup.to_dict()
        source_url_str = str(startup.source.url)
        norm_url = normalize_url(source_url_str)
        fp = url_fingerprint(source_url_str)

        # Attach helper and provenance fields
        startup_dict["url_fingerprint"] = fp
        startup_dict["source_url"] = norm_url
        if provenance:
            startup_dict["provenance"] = provenance
        else:
            startup_dict["provenance"] = {
                "is_qualified": True,
                "category": "STARTUP_COMPANY",
                "reasons": ["GitHub Organization record"],
            }

        # Pre-check existence
        if self.exists(source_url_str, startup.content.entityName):
            logger.info("startup_duplicate_skipped", url=norm_url, name=startup.content.entityName)
            return False

        try:
            col.insert_one(startup_dict)
            logger.info("startup_inserted", url=norm_url, name=startup.content.entityName)
            return True
        except DuplicateKeyError:
            logger.info("startup_duplicate_key_error", url=norm_url)
            return False
        except Exception as exc:
            logger.error("startup_insert_failed", url=norm_url, error=str(exc))
            raise

    def save_batch(
        self,
        startups: list[tuple[Startup, dict | None]],
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """Save a batch of Startup records into MongoDB with bulk insert and deduplication.

        Returns (inserted_count, duplicate_count).
        """
        if not startups:
            return (0, 0)

        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        seen_fps: set[str] = set()
        seen_names: set[str] = set()
        docs_to_insert: list[dict] = []
        duplicate_count = 0

        for startup, provenance in startups:
            url_str = str(startup.source.url)
            fp = url_fingerprint(url_str)
            norm_url = normalize_url(url_str)
            ent_name = startup.content.entityName

            # In-batch deduplication
            if fp in seen_fps or (ent_name and ent_name in seen_names):
                duplicate_count += 1
                continue
            seen_fps.add(fp)
            if ent_name:
                seen_names.add(ent_name)

            # DB existence check
            if self.exists(url_str, ent_name):
                duplicate_count += 1
                continue

            startup_dict = startup.to_dict()
            startup_dict["url_fingerprint"] = fp
            startup_dict["source_url"] = norm_url
            startup_dict["provenance"] = provenance or {
                "is_qualified": True,
                "category": "STARTUP_COMPANY",
                "reasons": ["GitHub Organization record"],
            }
            docs_to_insert.append(startup_dict)

        if not docs_to_insert:
            return (0, duplicate_count)

        if dry_run:
            logger.info("startup_dry_run_batch", candidate_count=len(docs_to_insert))
            return (len(docs_to_insert), duplicate_count)

        try:
            res = col.insert_many(docs_to_insert, ordered=False)
            inserted = len(res.inserted_ids)
            logger.info("startup_batch_inserted", count=inserted, duplicates=duplicate_count)
            return (inserted, duplicate_count)
        except DuplicateKeyError as dup_exc:
            inserted = dup_exc.details.get("nInserted", 0) if dup_exc.details else 0
            duplicate_count += len(docs_to_insert) - inserted
            return (inserted, duplicate_count)

    def close(self) -> None:
        """Close MongoDB connection client."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
