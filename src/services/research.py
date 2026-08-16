"""Research paper ingestion service — orchestrates adapter, parsing, validation, and storage."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import ValidationError

from src.config.settings import Settings
from src.crawlers.research import ResearchAdapter
from src.models.research_paper import ResearchPaper
from src.storage.repositories.research import ResearchPaperRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResearchService:
    """Orchestrates research paper discovery, GitHub metadata enrichment, Pydantic validation, and MongoDB persistence."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

import time
from src.config.settings import Settings
from src.crawlers.research import ResearchAdapter
from src.models.research_paper import ResearchPaper
from src.storage.checkpoints import Checkpoint, CheckpointRepository
from src.storage.repositories.research import ResearchPaperRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResearchService:
    """Orchestrates research paper discovery, GitHub metadata enrichment, Pydantic validation, and MongoDB persistence."""

    VERTICAL = "research"
    SOURCE = "arXiv"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def ingest(
        self,
        limit: int = 10,
        batch_size: int = 50,
        resume: bool = True,
        dry_run: bool = False,
        workers: int = 5,
    ) -> dict:
        """Ingest research papers up to `limit` with resumable checkpointing and batching."""
        logger.info(
            "research_ingestion_started",
            limit=limit,
            batch_size=batch_size,
            resume=resume,
            dry_run=dry_run,
        )

        start_time = time.monotonic()
        adapter = ResearchAdapter(settings=self.settings)
        repo = ResearchPaperRepository(settings=self.settings)
        cp_repo = CheckpointRepository(settings=self.settings)

        try:
            repo.setup_indexes()
            cp_repo.setup_indexes()

            cursor = 0
            inserted_count = 0
            duplicate_count = 0
            invalid_count = 0
            failed_count = 0
            processed_count = 0
            discovered_total = 0
            github_count = 0
            github_stars_count = 0

            # Checkpoint resolution
            if resume:
                cp = cp_repo.get_checkpoint(self.VERTICAL, self.SOURCE)
                if cp and cp.status != "completed":
                    cursor = cp.cursor
                    processed_count = cp.processed_count
                    inserted_count = cp.inserted_count
                    duplicate_count = cp.duplicate_count
                    invalid_count = cp.invalid_count
                    failed_count = cp.failed_count
                    logger.info("research_ingestion_resuming", checkpoint=cp.to_dict())
            else:
                cp_repo.reset_checkpoint(self.VERTICAL, self.SOURCE)

            target = limit

            while processed_count < target:
                fetch_limit = min(batch_size, target - processed_count)
                if fetch_limit <= 0:
                    break

                raw_papers = await adapter.discover_papers(limit=fetch_limit, start=cursor)
                if not raw_papers:
                    logger.info("research_no_more_data", cursor=cursor)
                    break

                discovered_total += len(raw_papers)
                valid_papers: list[ResearchPaper] = []

                for raw in raw_papers:
                    processed_count += 1
                    if raw.github_url:
                        github_count += 1
                    if raw.github_stars is not None:
                        github_stars_count += 1

                    try:
                        collected_at = datetime.now(timezone.utc)
                        paper = ResearchPaper(
                            content={
                                "title": raw.title,
                                "authors": raw.authors,
                                "paper_url": raw.paper_url,
                                "github_url": raw.github_url,
                                "github_stars": raw.github_stars,
                                "published_date": raw.published_date or collected_at,
                            },
                            collectedAt=collected_at,
                        )
                        valid_papers.append(paper)
                    except ValidationError as val_err:
                        invalid_count += 1
                        logger.warning(
                            "research_paper_validation_failed",
                            error=str(val_err),
                            title=raw.title,
                        )
                    except Exception as exc:
                        failed_count += 1
                        logger.error(
                            "research_paper_processing_failed",
                            error=str(exc),
                            title=raw.title,
                        )

                # Batch save
                b_inserted, b_duplicates = repo.save_batch(valid_papers, dry_run=dry_run)
                inserted_count += b_inserted
                duplicate_count += b_duplicates
                cursor += len(raw_papers)

                # Update Checkpoint
                cp_status = "completed" if processed_count >= target else "running"
                cp_repo.save_checkpoint(
                    Checkpoint(
                        vertical=self.VERTICAL,
                        source=self.SOURCE,
                        cursor=cursor,
                        processed_count=processed_count,
                        inserted_count=inserted_count,
                        duplicate_count=duplicate_count,
                        invalid_count=invalid_count,
                        failed_count=failed_count,
                        last_successful_item=raw_papers[-1].title if raw_papers else "",
                        status=cp_status,
                    )
                )

            duration = round(time.monotonic() - start_time, 2)
            throughput = round(processed_count / max(duration, 0.001), 2)
            final_status = "success" if processed_count >= target else "partial"

            result = {
                "status": final_status,
                "vertical": self.VERTICAL,
                "source": self.SOURCE,
                "requested": limit,
                "discovered": discovered_total,
                "processed": processed_count,
                "valid": len(valid_papers) if 'valid_papers' in locals() else 0,
                "inserted": inserted_count,
                "duplicates": duplicate_count,
                "invalid": invalid_count,
                "failed": failed_count,
                "github_count": github_count,
                "github_stars_count": github_stars_count,
                "count": inserted_count,
                "duration_seconds": duration,
                "throughput_per_sec": throughput,
                "dry_run": dry_run,
            }

            logger.info("research_ingestion_completed", **result)
            return result

        except KeyboardInterrupt:
            logger.warning("research_ingestion_interrupted")
            cp_repo.save_checkpoint(
                Checkpoint(
                    vertical=self.VERTICAL,
                    source=self.SOURCE,
                    cursor=cursor if 'cursor' in locals() else 0,
                    processed_count=processed_count if 'processed_count' in locals() else 0,
                    inserted_count=inserted_count if 'inserted_count' in locals() else 0,
                    duplicate_count=duplicate_count if 'duplicate_count' in locals() else 0,
                    invalid_count=invalid_count if 'invalid_count' in locals() else 0,
                    failed_count=failed_count if 'failed_count' in locals() else 0,
                    status="interrupted",
                )
            )
            raise
        except Exception as exc:
            logger.error("research_ingestion_failed", error=str(exc))
            return {"status": "error", "count": 0, "error": str(exc)}
        finally:
            await adapter.close()
            repo.close()
            cp_repo.close()
