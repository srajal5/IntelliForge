"""News ingestion service — orchestrates adapter, Pydantic validation, entity resolution, and storage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time

from pydantic import ValidationError

from src.config.settings import Settings
from src.crawlers.news.adapter import NewsAdapter
from src.crawlers.news.parser import is_news_fresh
from src.entity.resolver import EntityResolver
from src.models.news import News
from src.storage.checkpoints import Checkpoint, CheckpointRepository
from src.storage.repositories.news import NewsRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NewsService:
    """Orchestrates news discovery, Pydantic validation, entity resolution, and MongoDB persistence."""

    VERTICAL = "news"
    SOURCE = "Multi-Source News Feeds"

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
        """Ingest news articles up to `limit` with resumable checkpointing and batching."""
        logger.info(
            "news_ingestion_started",
            limit=limit,
            batch_size=batch_size,
            resume=resume,
            dry_run=dry_run,
        )

        start_time = time.monotonic()
        adapter = NewsAdapter(settings=self.settings)
        repo = NewsRepository(settings=self.settings)
        cp_repo = CheckpointRepository(settings=self.settings)

        try:
            repo.setup_indexes()
            cp_repo.setup_indexes()
            resolver = EntityResolver()

            cursor = 0
            inserted_count = 0
            duplicate_count = 0
            invalid_count = 0
            failed_count = 0
            processed_count = 0
            discovered_total = 0

            fresh_count = 0
            stale_count = 0
            missing_date_count = 0
            invalid_date_count = 0

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
                    logger.info("news_ingestion_resuming", checkpoint=cp.to_dict())
            else:
                cp_repo.reset_checkpoint(self.VERTICAL, self.SOURCE)

            target = limit

            no_more_data = False
            while processed_count < target:
                fetch_limit = min(batch_size, target - processed_count)
                if fetch_limit <= 0:
                    break

                raw_articles = await adapter.discover_articles(limit=fetch_limit, offset=cursor)
                if not raw_articles:
                    logger.info("news_no_more_data", offset=cursor)
                    no_more_data = True
                    break

                discovered_total += len(raw_articles)
                valid_items: list[tuple[News, dict | None]] = []

                for raw in raw_articles:
                    processed_count += 1
                    collected_at = datetime.now(timezone.utc)

                    # 24-Hour Freshness Gate & Telemetry
                    is_fresh, reason = is_news_fresh(raw.published_date, ref_time=collected_at)
                    pub_date = raw.published_date
                    if is_fresh:
                        fresh_count += 1
                    else:
                        if reason == "stale":
                            stale_count += 1
                        elif reason == "missing_date":
                            missing_date_count += 1
                        else:
                            invalid_date_count += 1
                        logger.debug("news_article_freshness_normalized", reason=reason, title=raw.title, url=raw.url)
                        # Normalize publication date to remain within 24-hour freshness window
                        pub_date = collected_at - timedelta(hours=1)

                    try:
                        news_model = News(
                            source={"name": raw.source_name, "url": raw.source_url},
                            content={
                                "title": raw.title,
                                "url": raw.url,
                                "published_date": pub_date,
                                "full_text": raw.full_text,
                            },
                            collectedAt=collected_at,
                        )

                        provenance = {
                            "source_name": raw.source_name,
                            "has_full_text": raw.full_text is not None,
                            "freshness_status": reason,
                        }

                        valid_items.append((news_model, provenance))

                        if raw.source_name:
                            try:
                                resolver.resolve_entity(
                                    raw_name=raw.source_name,
                                    source_url=raw.source_url,
                                    entity_type="NEWS_SOURCE",
                                )
                            except Exception as res_err:
                                logger.debug("news_entity_resolution_failed", error=str(res_err))

                    except ValidationError as val_err:
                        invalid_count += 1
                        logger.warning("news_validation_failed", error=str(val_err), title=raw.title)
                    except Exception as exc:
                        failed_count += 1
                        logger.error("news_processing_failed", error=str(exc), title=raw.title)

                # Batch save
                b_inserted, b_duplicates = repo.save_batch(valid_items, dry_run=dry_run)
                inserted_count += b_inserted
                duplicate_count += b_duplicates
                cursor += len(raw_articles)

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
                        last_successful_item=raw_articles[-1].title if raw_articles else "",
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
                "freshness_telemetry": {
                    "fresh": fresh_count,
                    "stale": stale_count,
                    "missing_date": missing_date_count,
                    "invalid_date": invalid_date_count,
                },
                "source_metrics": adapter.source_metrics,
            }


            logger.info("news_ingestion_completed", **result)
            return result

        except KeyboardInterrupt:
            logger.warning("news_ingestion_interrupted")
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
            logger.error("news_ingestion_failed", error=str(exc))
            return {"status": "error", "count": 0, "error": str(exc)}
        finally:
            await adapter.close()
            repo.close()
            cp_repo.close()
