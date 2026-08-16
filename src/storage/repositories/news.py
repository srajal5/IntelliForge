"""MongoDB repository for storing and deduplicating News canonical records."""

from __future__ import annotations

from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

from src.config.settings import Settings, get_settings
from src.crawlers.fingerprint import normalize_url, url_fingerprint
from src.models.news import News
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NewsRepository:
    """Handles persistence, unique indexing, and deduplication for News records in MongoDB."""

    COLLECTION_NAME = "news"

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
        """Create unique index on content.url and url_fingerprint for deduplication."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            col.create_index([("content.url", ASCENDING)], unique=True, sparse=True)
            col.create_index([("url_fingerprint", ASCENDING)], unique=True, sparse=True)
            col.create_index([("content.published_date", ASCENDING)], sparse=True)
            logger.info("news_repository_indexes_setup")
        except Exception as exc:
            logger.warning("news_repository_indexes_failed", error=str(exc))

    def exists(self, article_url: str) -> bool:
        """Check if a news article already exists in MongoDB by URL or fingerprint."""
        if not article_url:
            return False
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            norm_url = normalize_url(article_url)
            fp = url_fingerprint(article_url)

            query = {
                "$or": [
                    {"content.url": norm_url},
                    {"content.url": article_url},
                    {"url_fingerprint": fp},
                ]
            }
            return col.count_documents(query, limit=1) > 0
        except Exception as exc:
            logger.error("news_repository_exists_check_failed", url=article_url, error=str(exc))
            return False

    def save(self, news: News, provenance: dict | None = None) -> bool:
        """Save a validated News record into MongoDB.

        Returns True if inserted, False if duplicate.
        """
        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        news_dict = news.to_dict()
        url_str = str(news.content.url)
        norm_url = normalize_url(url_str)
        fp = url_fingerprint(url_str)

        # Attach helper and provenance fields
        news_dict["url_fingerprint"] = fp
        news_dict["source_url"] = str(news.source.url)
        news_dict["provenance"] = provenance or {
            "source_name": news.source.name,
            "has_full_text": news.content.full_text is not None,
        }

        # Pre-check existence
        if self.exists(url_str):
            logger.info("news_duplicate_skipped", url=norm_url, title=news.content.title)
            return False

        try:
            col.insert_one(news_dict)
            logger.info("news_inserted", url=norm_url, title=news.content.title)
            return True
        except DuplicateKeyError:
            logger.info("news_duplicate_key_error", url=norm_url)
            return False
        except Exception as exc:
            logger.error("news_insert_failed", url=norm_url, error=str(exc))
            raise

    def save_batch(
        self,
        articles: list[tuple[News, dict | None]],
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """Save a batch of News records into MongoDB with bulk insert and deduplication.

        Returns (inserted_count, duplicate_count).
        """
        if not articles:
            return (0, 0)

        db = self._get_db()
        col = db[self.COLLECTION_NAME]

        seen_fps: set[str] = set()
        docs_to_insert: list[dict] = []
        duplicate_count = 0

        for news, provenance in articles:
            url_str = str(news.content.url)
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

            news_dict = news.to_dict()
            news_dict["url_fingerprint"] = fp
            news_dict["source_url"] = str(news.source.url)
            news_dict["provenance"] = provenance or {
                "source_name": news.source.name,
                "has_full_text": news.content.full_text is not None,
            }
            docs_to_insert.append(news_dict)

        if not docs_to_insert:
            return (0, duplicate_count)

        if dry_run:
            logger.info("news_dry_run_batch", candidate_count=len(docs_to_insert))
            return (len(docs_to_insert), duplicate_count)

        try:
            res = col.insert_many(docs_to_insert, ordered=False)
            inserted = len(res.inserted_ids)
            logger.info("news_batch_inserted", count=inserted, duplicates=duplicate_count)
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
