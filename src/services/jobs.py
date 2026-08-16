"""Jobs ingestion service — orchestrates adapter, Pydantic validation, entity resolution, and storage."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import ValidationError

from src.config.settings import Settings
from src.crawlers.jobs.adapter import JobsAdapter
from src.entity.resolver import EntityResolver
from src.models.job import Job
from src.storage.repositories.jobs import JobRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobsService:
    """Orchestrates job discovery, Pydantic validation, entity resolution, and MongoDB persistence."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

import time
from src.config.settings import Settings
from src.crawlers.jobs.adapter import JobsAdapter
from src.entity.resolver import EntityResolver
from src.models.job import Job
from src.storage.checkpoints import Checkpoint, CheckpointRepository
from src.storage.repositories.jobs import JobRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobsService:
    """Orchestrates job discovery, Pydantic validation, entity resolution, and MongoDB persistence."""

    VERTICAL = "jobs"
    SOURCE = "Multi-Source Job Boards"

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
        """Ingest job postings up to `limit` with resumable checkpointing and batching."""
        logger.info(
            "jobs_ingestion_started",
            limit=limit,
            batch_size=batch_size,
            resume=resume,
            dry_run=dry_run,
        )

        start_time = time.monotonic()
        adapter = JobsAdapter(settings=self.settings)
        repo = JobRepository(settings=self.settings)
        cp_repo = CheckpointRepository(settings=self.settings)

        try:
            repo.setup_indexes()
            cp_repo.setup_indexes()
            resolver = EntityResolver()

            cursor = 1  # Page-based
            inserted_count = 0
            duplicate_count = 0
            invalid_count = 0
            failed_count = 0
            processed_count = 0
            discovered_total = 0

            # Checkpoint resolution
            if resume:
                cp = cp_repo.get_checkpoint(self.VERTICAL, self.SOURCE)
                if cp and cp.status != "completed":
                    cursor = max(1, cp.cursor)
                    processed_count = cp.processed_count
                    inserted_count = cp.inserted_count
                    duplicate_count = cp.duplicate_count
                    invalid_count = cp.invalid_count
                    failed_count = cp.failed_count
                    logger.info("jobs_ingestion_resuming", checkpoint=cp.to_dict())
            else:
                cp_repo.reset_checkpoint(self.VERTICAL, self.SOURCE)

            target = limit

            no_more_data = False
            while processed_count < target:
                fetch_limit = min(batch_size, target - processed_count)
                if fetch_limit <= 0:
                    break

                raw_jobs = await adapter.discover_jobs(limit=fetch_limit, offset=(cursor - 1) * fetch_limit)
                if not raw_jobs:
                    logger.info("jobs_no_more_data", page=cursor)
                    no_more_data = True
                    break

                discovered_total += len(raw_jobs)
                valid_items: list[tuple[Job, str, dict | None]] = []

                for raw in raw_jobs:
                    processed_count += 1
                    try:
                        collected_at = datetime.now(timezone.utc)
                        job_model = Job(
                            content={
                                "company": raw.company,
                                "date": raw.date,
                                "is_remote": raw.is_remote,
                                "role_family": raw.role_family,
                            },
                            collectedAt=collected_at,
                        )
                        provenance = {
                            "company": raw.company,
                            "title": raw.title,
                            "is_remote": raw.is_remote,
                            "role_family": raw.role_family,
                        }
                        valid_items.append((job_model, raw.url, provenance))

                        if raw.company:
                            try:
                                resolver.resolve_entity(
                                    raw_name=raw.company,
                                    source_url=raw.url,
                                    entity_type="COMPANY",
                                )
                            except Exception as res_err:
                                logger.debug("job_entity_resolution_failed", error=str(res_err))

                    except ValidationError as val_err:
                        invalid_count += 1
                        logger.warning("job_validation_failed", error=str(val_err), company=raw.company, title=raw.title)
                    except Exception as exc:
                        failed_count += 1
                        logger.error("job_processing_failed", error=str(exc), company=raw.company, title=raw.title)

                # Batch save
                b_inserted, b_duplicates = repo.save_batch(valid_items, dry_run=dry_run)
                inserted_count += b_inserted
                duplicate_count += b_duplicates
                cursor += 1

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
                        last_successful_item=raw_jobs[-1].title if raw_jobs else "",
                        status=cp_status,
                    )
                )

            duration = round(time.monotonic() - start_time, 2)
            throughput = round(processed_count / max(duration, 0.001), 2)
            final_status = "success" if (processed_count >= target or no_more_data) else "partial"

            result = {
                "status": final_status,
                "vertical": self.VERTICAL,
                "source": self.SOURCE,
                "requested": limit,
                "discovered": discovered_total,
                "processed": processed_count,
                "valid": len(valid_items) if 'valid_items' in locals() else 0,
                "inserted": inserted_count,
                "duplicates": duplicate_count,
                "invalid": invalid_count,
                "failed": failed_count,
                "count": inserted_count,
                "duration_seconds": duration,
                "throughput_per_sec": throughput,
                "dry_run": dry_run,
                "source_metrics": adapter.source_metrics,
            }

            logger.info("jobs_ingestion_completed", **result)
            return result

        except KeyboardInterrupt:
            logger.warning("jobs_ingestion_interrupted")
            cp_repo.save_checkpoint(
                Checkpoint(
                    vertical=self.VERTICAL,
                    source=self.SOURCE,
                    cursor=cursor if 'cursor' in locals() else 1,
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
            logger.error("jobs_ingestion_failed", error=str(exc))
            return {"status": "error", "count": 0, "error": str(exc)}
        finally:
            await adapter.close()
            repo.close()
            cp_repo.close()
