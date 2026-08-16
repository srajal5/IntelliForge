"""Checkpoint system for resumable ingestion tracking in MongoDB."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

from src.config.settings import Settings, get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Checkpoint:
    """Represents the progress checkpoint of an ingestion process."""

    vertical: str
    source: str
    cursor: int = 0  # Page number or offset index
    segment: int = 0  # Query/topic segment index
    processed_count: int = 0
    inserted_count: int = 0
    duplicate_count: int = 0
    invalid_count: int = 0
    failed_count: int = 0
    last_successful_item: str = ""
    status: str = "running"  # running, completed, failed, interrupted
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MongoDB persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """Construct Checkpoint from MongoDB dictionary."""
        data_copy = {k: v for k, v in data.items() if k != "_id"}
        return cls(**data_copy)


class CheckpointRepository:
    """Handles persistence and retrieval of ingestion checkpoints in MongoDB."""

    COLLECTION_NAME = "checkpoints"

    def __init__(
        self,
        settings: Settings | None = None,
        client: MongoClient | None = None,
    ) -> None:
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
        """Ensure unique compound index on (vertical, source)."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            col.create_index(
                [("vertical", ASCENDING), ("source", ASCENDING)],
                unique=True,
            )
            logger.info("checkpoint_indexes_setup")
        except Exception as exc:
            logger.warning("checkpoint_indexes_failed", error=str(exc))

    def get_checkpoint(self, vertical: str, source: str) -> Checkpoint | None:
        """Retrieve existing checkpoint for vertical + source, or None."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            doc = col.find_one({"vertical": vertical, "source": source})
            if doc:
                return Checkpoint.from_dict(doc)
            return None
        except Exception as exc:
            logger.error(
                "get_checkpoint_failed",
                vertical=vertical,
                source=source,
                error=str(exc),
            )
            return None

    def save_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Save or update checkpoint in MongoDB."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            checkpoint.updated_at = datetime.now(timezone.utc).isoformat()
            query = {"vertical": checkpoint.vertical, "source": checkpoint.source}
            col.update_one(query, {"$set": checkpoint.to_dict()}, upsert=True)
            logger.debug(
                "checkpoint_saved",
                vertical=checkpoint.vertical,
                source=checkpoint.source,
                cursor=checkpoint.cursor,
                inserted=checkpoint.inserted_count,
            )
            return True
        except Exception as exc:
            logger.error(
                "save_checkpoint_failed",
                vertical=checkpoint.vertical,
                source=checkpoint.source,
                error=str(exc),
            )
            return False

    def reset_checkpoint(self, vertical: str, source: str) -> bool:
        """Delete/reset checkpoint for vertical + source."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            col.delete_one({"vertical": vertical, "source": source})
            logger.info("checkpoint_reset", vertical=vertical, source=source)
            return True
        except Exception as exc:
            logger.error(
                "reset_checkpoint_failed",
                vertical=vertical,
                source=source,
                error=str(exc),
            )
            return False

    def get_all_checkpoints(self) -> list[dict[str, Any]]:
        """Retrieve all checkpoints from MongoDB as dictionaries."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            return list(col.find({}, {"_id": 0}))
        except Exception as exc:
            logger.error("get_all_checkpoints_failed", error=str(exc))
            return []

    def reset_all(self, vertical: str | None = None) -> int:
        """Reset checkpoints for a specific vertical or all verticals."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION_NAME]
            query = {"vertical": vertical} if vertical else {}
            res = col.delete_many(query)
            return res.deleted_count
        except Exception as exc:
            logger.error("reset_all_checkpoints_failed", error=str(exc))
            return 0

    def close(self) -> None:
        """Close MongoDB connection client."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
