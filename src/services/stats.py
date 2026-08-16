"""Database statistics service."""

from __future__ import annotations

from src.config.settings import Settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

COLLECTIONS = [
    "startups",
    "products",
    "research_papers",
    "jobs",
    "news",
    "entity_mappings",
]


class StatsService:
    """Retrieves collection counts and quality metrics from MongoDB."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_stats(self) -> dict | None:
        """Return collection counts and quality metrics, or None on connection failure."""
        try:
            from pymongo import MongoClient

            client = MongoClient(
                self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
            )
            db = client[self.settings.mongodb_database]

            counts: dict[str, int] = {}
            for col in COLLECTIONS:
                counts[col] = db[col].count_documents({})

            quality = self._compute_quality(db, counts)
            client.close()
            logger.info("stats_retrieved", counts=counts)
            return {"collections": counts, "quality": quality}

        except Exception as exc:
            logger.error("stats_connection_failed", error=str(exc))
            return None

    # ------------------------------------------------------------------

    @staticmethod
    def _compute_quality(db, counts: dict) -> dict:
        """Derive quality metrics from the database."""
        quality: dict[str, int] = {}

        # Valid records (those without a 'validation_error' flag)
        for col in ("startups", "products", "research_papers", "jobs", "news"):
            if counts.get(col, 0) > 0:
                valid = db[col].count_documents({"validation_error": {"$exists": False}})
                quality[f"valid_{col}"] = valid

        # Duplicate records
        dup_count = db["entity_mappings"].count_documents({"is_duplicate": True})
        quality["duplicate_records"] = dup_count

        # Missing source URLs
        missing_url = 0
        for col in ("startups", "products", "research_papers", "jobs", "news"):
            missing_url += db[col].count_documents(
                {"source_url": {"$in": [None, ""]}}
            )
        quality["missing_source_urls"] = missing_url

        # Research papers with GitHub info
        quality["research_with_github"] = db["research_papers"].count_documents(
            {"$or": [
                {"github_url": {"$exists": True, "$ne": None, "$ne": ""}},
                {"content.github_url": {"$exists": True, "$ne": None, "$ne": ""}},
            ]}
        )
        quality["research_with_stars"] = db["research_papers"].count_documents(
            {"$or": [
                {"github_stars": {"$exists": True, "$ne": None, "$gt": 0}},
                {"content.github_stars": {"$exists": True, "$ne": None, "$gt": 0}},
            ]}
        )

        # Freshness
        quality["total_news"] = counts.get("news", 0)
        quality["total_jobs"] = counts.get("jobs", 0)

        return quality
