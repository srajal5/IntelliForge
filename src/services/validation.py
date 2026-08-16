"""Data-quality validation service."""

from __future__ import annotations

from src.config.settings import Settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationService:
    """Runs data-quality checks against MongoDB and reports issues."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate(self) -> dict:
        """Run full validation. Returns dict with 'passed' bool and 'report'."""
        try:
            from pymongo import MongoClient

            client = MongoClient(
                self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
            )
            db = client[self.settings.mongodb_database]
            report = self._build_report(db)
            client.close()

            critical_failures = (
                report.get("invalid_records", 0) > 0
                or report.get("llm_failures", 0) > 0
            )
            passed = not critical_failures
            logger.info("validation_complete", passed=passed, report=report)
            return {"passed": passed, "report": report}

        except Exception as exc:
            logger.error("validation_connection_failed", error=str(exc))
            return {
                "passed": False,
                "report": {"error": f"MongoDB connection failed: {exc}"},
            }

    # ------------------------------------------------------------------

    @staticmethod
    def _build_report(db) -> dict:
        report: dict[str, int] = {}

        # Collection counts
        for col in ("startups", "products", "research_papers", "jobs", "news"):
            report[col] = db[col].count_documents({})

        report["entity_mappings"] = db["entity_mappings"].count_documents({})
        report["duplicates"] = db["entity_mappings"].count_documents(
            {"is_duplicate": True}
        )

        # Quality checks
        report["invalid_records"] = 0
        for col in ("startups", "products", "research_papers", "jobs", "news"):
            report["invalid_records"] += db[col].count_documents(
                {"validation_error": {"$exists": True}}
            )

        report["stale_records"] = 0
        report["missing_source_urls"] = 0
        for col in ("startups", "products", "research_papers", "jobs", "news"):
            report["missing_source_urls"] += db[col].count_documents(
                {"source_url": {"$in": [None, ""]}}
            )

        report["llm_failures"] = 0
        for col in ("startups", "products", "research_papers", "jobs", "news"):
            report["llm_failures"] += db[col].count_documents(
                {"llm_error": {"$exists": True}}
            )

        report["unresolved_entities"] = db["entity_mappings"].count_documents(
            {"resolved": False}
        )

        return report
