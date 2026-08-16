"""Pipeline orchestration service.

Runs ingestion verticals in the correct order, followed by
entity resolution and validation.
"""

from __future__ import annotations

import time

from src.config.settings import Settings
from src.utils.logging import get_logger
from src.services.research import ResearchService
from src.services.startups import StartupsService
from src.services.products import ProductsService
from src.services.news import NewsService
from src.services.jobs import JobsService
from src.services.resolver import ResolverService
from src.services.validation import ValidationService

logger = get_logger(__name__)


class PipelineService:
    """Orchestrates the full ingestion pipeline."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(
        self,
        limit: int = 10,
        workers: int = 5,
        skip_research: bool = False,
        skip_startups: bool = False,
        skip_products: bool = False,
        skip_news: bool = False,
        skip_jobs: bool = False,
        source: str | None = None,
    ) -> dict:
        """Execute the pipeline in order. Returns results per stage."""
        logger.info("pipeline_started", limit=limit, workers=workers)
        start = time.perf_counter()
        results: dict[str, dict] = {}

        # If --source is set, only run that vertical
        if source:
            return await self._run_single(source, limit, workers)

        # 1. Research papers
        if not skip_research:
            results["research"] = await ResearchService(self.settings).ingest(limit, workers)

        # 2. Startups
        if not skip_startups:
            results["startups"] = await StartupsService(self.settings).ingest(limit, workers)

        # 3. Products
        if not skip_products:
            results["products"] = await ProductsService(self.settings).ingest(limit, workers)

        # 4. News
        if not skip_news:
            results["news"] = await NewsService(self.settings).ingest(limit, workers)

        # 5. Jobs
        if not skip_jobs:
            results["jobs"] = await JobsService(self.settings).ingest(limit, workers)

        # 6. Entity resolution
        results["resolution"] = await ResolverService(self.settings).resolve()

        # 7. Validation
        results["validation"] = ValidationService(self.settings).validate()

        elapsed = time.perf_counter() - start
        logger.info("pipeline_completed", elapsed_seconds=round(elapsed, 2))
        return {"stages": results, "elapsed_seconds": round(elapsed, 2)}

    async def _run_single(self, source: str, limit: int, workers: int) -> dict:
        """Run a single named source."""
        svc_map = {
            "research": ResearchService,
            "startups": StartupsService,
            "products": ProductsService,
            "news": NewsService,
            "jobs": JobsService,
        }
        cls = svc_map.get(source)
        if cls is None:
            return {"error": f"Unknown source: {source}. Options: {list(svc_map)}"}
        result = await cls(self.settings).ingest(limit, workers)
        return {"stages": {source: result}}
