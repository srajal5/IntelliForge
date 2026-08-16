"""Entity resolution service."""

from __future__ import annotations

from src.config.settings import Settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResolverService:
    """Orchestrates entity resolution across data sources."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def resolve(self) -> dict:
        """Run entity resolution. Returns summary dict."""
        logger.info("entity_resolution_started")
        try:
            from src.entity.resolver import EntityResolver  # type: ignore[attr-defined]

            resolver = EntityResolver(self.settings)
            result = await resolver.resolve_all()
            logger.info("entity_resolution_completed", result=result)
            return {"status": "success", **result}
        except (ImportError, AttributeError):
            logger.warning("entity_resolution_not_implemented")
            return {
                "status": "not_implemented",
                "processed": 0,
                "resolved": 0,
                "unresolved": 0,
                "exact_matches": 0,
                "alias_matches": 0,
                "fuzzy_matches": 0,
                "message": "Entity resolver not yet implemented",
            }
        except Exception as exc:
            logger.error("entity_resolution_failed", error=str(exc))
            return {"status": "error", "error": str(exc)}
