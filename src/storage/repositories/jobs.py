"""MongoDB repository for storing and deduplicating Job canonical records."""

from __future__ import annotations

from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

from src.config.settings import Settings, get_settings
from src.crawlers.fingerprint import normalize_url, url_fingerprint
from src.models.job import Job
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobRepository:
    """Handles persistence, unique indexing, and deduplication for Job records in MongoDB."""

    COLLECTION_NAME = "jobs"

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
        """Create unique indexes on url_fingerprint and source_url for deduplication."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            col.create_index([("url_fingerprint", ASCENDING)], unique=True, sparse=True)
            col.create_index([("source_url", ASCENDING)], unique=True, sparse=True)
            col.create_index([("content.company", ASCENDING)], sparse=True)
            col.create_index([("content.date", ASCENDING)], sparse=True)
            logger.info("job_repository_indexes_setup")
        except Exception as exc:
            logger.warning("job_repository_indexes_failed", error=str(exc))

    def exists(self, job_url: str) -> bool:
        """Check if a job posting already exists in MongoDB by URL or fingerprint."""
        if not job_url:
            return False
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            norm_url = normalize_url(job_url)
            fp = url_fingerprint(job_url)

            query = {
                "$or": [
                    {"source_url": norm_url},
                    {"source_url": job_url},
                    {"url_fingerprint": fp},
                ]
            }
            return col.count_documents(query, limit=1) > 0
        except Exception as exc:
            logger.error("job_repository_exists_check_failed", url=job_url, error=str(exc))
            return False

    def save(self, job: Job, source_url: str, provenance: dict | None = None) -> bool:
        """Save a validated Job record into MongoDB.

        Returns True if inserted, False if duplicate.
        """
        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        job_dict = job.to_dict()
        norm_url = normalize_url(source_url)
        fp = url_fingerprint(source_url)

        # Attach helper and provenance fields
        job_dict["url_fingerprint"] = fp
        job_dict["source_url"] = norm_url
        job_dict["provenance"] = provenance or {
            "company": job.content.company,
            "is_remote": job.content.is_remote,
            "role_family": job.content.role_family,
        }

        # Pre-check existence
        if self.exists(source_url):
            logger.info("job_duplicate_skipped", url=norm_url, company=job.content.company)
            return False

        try:
            col.insert_one(job_dict)
            logger.info("job_inserted", url=norm_url, company=job.content.company)
            return True
        except DuplicateKeyError:
            logger.info("job_duplicate_key_error", url=norm_url)
            return False
        except Exception as exc:
            logger.error("job_insert_failed", url=norm_url, error=str(exc))
            raise

    def save_batch(
        self,
        jobs: list[tuple[Job, str, dict | None]],
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """Save a batch of Job records into MongoDB with bulk insert and deduplication.

        Returns (inserted_count, duplicate_count).
        """
        if not jobs:
            return (0, 0)

        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        seen_fps: set[str] = set()
        docs_to_insert: list[dict] = []
        duplicate_count = 0

        for job, source_url, provenance in jobs:
            fp = url_fingerprint(source_url)
            norm_url = normalize_url(source_url)

            # In-batch deduplication
            if fp in seen_fps:
                duplicate_count += 1
                continue
            seen_fps.add(fp)

            # DB existence check
            if self.exists(source_url):
                duplicate_count += 1
                continue

            job_dict = job.to_dict()
            job_dict["url_fingerprint"] = fp
            job_dict["source_url"] = norm_url
            job_dict["provenance"] = provenance or {
                "company": job.content.company,
                "is_remote": job.content.is_remote,
                "role_family": job.content.role_family,
            }
            docs_to_insert.append(job_dict)

        if not docs_to_insert:
            return (0, duplicate_count)

        if dry_run:
            logger.info("job_dry_run_batch", candidate_count=len(docs_to_insert))
            return (len(docs_to_insert), duplicate_count)

        try:
            res = col.insert_many(docs_to_insert, ordered=False)
            inserted = len(res.inserted_ids)
            logger.info("job_batch_inserted", count=inserted, duplicates=duplicate_count)
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
