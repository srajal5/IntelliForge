"""MongoDB repository for storing and deduplicating ResearchPaper canonical records."""

from __future__ import annotations

from typing import Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

from src.config.settings import Settings, get_settings
from src.crawlers.fingerprint import normalize_url, url_fingerprint
from src.models.research_paper import ResearchPaper
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResearchPaperRepository:
    """Handles persistence, unique indexing, and deduplication for ResearchPaper records in MongoDB."""

    COLLECTION_NAME = "research_papers"

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
        """Create unique index on content.paper_url for deduplication."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            col.create_index([("content.paper_url", ASCENDING)], unique=True, sparse=True)
            col.create_index([("url_fingerprint", ASCENDING)], unique=True, sparse=True)
            logger.info("research_repository_indexes_setup")
        except Exception as exc:
            logger.warning("research_repository_indexes_failed", error=str(exc))

    def exists(self, paper_url: str) -> bool:
        """Check if a research paper already exists in MongoDB by canonical paper URL or fingerprint."""
        if not paper_url:
            return False
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            norm_url = normalize_url(paper_url)
            fp = url_fingerprint(paper_url)

            query = {
                "$or": [
                    {"content.paper_url": norm_url},
                    {"content.paper_url": paper_url},
                    {"url_fingerprint": fp},
                ]
            }
            return col.count_documents(query, limit=1) > 0
        except Exception as exc:
            logger.error("research_repository_exists_check_failed", url=paper_url, error=str(exc))
            return False

    def save(self, paper: ResearchPaper) -> bool:
        """Save a validated ResearchPaper record into MongoDB.

        Returns True if inserted, False if duplicate.
        """
        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        paper_dict = paper.to_dict()
        norm_url = normalize_url(str(paper.content.paper_url))
        fp = url_fingerprint(str(paper.content.paper_url))

        # Attach url_fingerprint and denormalized root fields for query convenience
        paper_dict["url_fingerprint"] = fp
        paper_dict["source_url"] = norm_url
        paper_dict["github_url"] = str(paper.content.github_url) if paper.content.github_url else None
        paper_dict["github_stars"] = paper.content.github_stars

        # Pre-check existence
        if self.exists(str(paper.content.paper_url)):
            logger.info("research_paper_duplicate_skipped", url=norm_url)
            return False

        try:
            col.insert_one(paper_dict)
            logger.info("research_paper_inserted", url=norm_url)
            return True
        except DuplicateKeyError:
            logger.info("research_paper_duplicate_key_error", url=norm_url)
            return False
        except Exception as exc:
            logger.error("research_paper_insert_failed", url=norm_url, error=str(exc))
            raise

    def save_batch(self, papers: list[ResearchPaper], dry_run: bool = False) -> tuple[int, int]:
        """Save a batch of ResearchPaper records into MongoDB with bulk insert and deduplication.

        Returns (inserted_count, duplicate_count).
        """
        if not papers:
            return (0, 0)

        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        seen_fps: set[str] = set()
        docs_to_insert: list[dict[str, Any]] = []
        duplicate_count = 0

        for paper in papers:
            url_str = str(paper.content.paper_url)
            fp = url_fingerprint(url_str)
            norm_url = normalize_url(url_str)

            # In-batch deduplication
            if fp in seen_fps:
                duplicate_count += 1
                continue
            seen_fps.add(fp)

            # DB existence check
            if self.exists(url_str):
                duplicate_count += 1
                continue

            paper_dict = paper.to_dict()
            paper_dict["url_fingerprint"] = fp
            paper_dict["source_url"] = norm_url
            paper_dict["github_url"] = str(paper.content.github_url) if paper.content.github_url else None
            paper_dict["github_stars"] = paper.content.github_stars
            docs_to_insert.append(paper_dict)

        if not docs_to_insert:
            return (0, duplicate_count)

        if dry_run:
            logger.info("research_paper_dry_run_batch", candidate_count=len(docs_to_insert))
            return (len(docs_to_insert), duplicate_count)

        try:
            res = col.insert_many(docs_to_insert, ordered=False)
            inserted = len(res.inserted_ids)
            logger.info("research_paper_batch_inserted", count=inserted, duplicates=duplicate_count)
            return (inserted, duplicate_count)
        except DuplicateKeyError as dup_exc:
            # Handle partial bulk insert duplicate keys gracefully
            inserted = dup_exc.details.get("nInserted", 0) if dup_exc.details else 0
            duplicate_count += len(docs_to_insert) - inserted
            return (inserted, duplicate_count)

    def close(self) -> None:
        """Close MongoDB connection client."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
