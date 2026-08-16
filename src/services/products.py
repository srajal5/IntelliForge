"""Products ingestion service — orchestrates adapter, Pydantic validation, and storage."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pydantic import ValidationError

from src.config.settings import Settings
from src.crawlers.products import ProductAdapter
from src.models.product import Product
from src.storage.checkpoints import Checkpoint, CheckpointRepository
from src.storage.repositories.products import ProductRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProductsService:
    """Orchestrates product discovery, Pydantic validation, and MongoDB persistence."""

    VERTICAL = "products"
    SOURCE = "GitHub Search"

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
        """Ingest products up to `limit` with resumable checkpointing and batching."""
        logger.info(
            "products_ingestion_started",
            limit=limit,
            batch_size=batch_size,
            resume=resume,
            dry_run=dry_run,
        )

        start_time = time.monotonic()
        adapter = ProductAdapter(settings=self.settings)
        repo = ProductRepository(settings=self.settings)
        cp_repo = CheckpointRepository(settings=self.settings)

        try:
            repo.setup_indexes()
            cp_repo.setup_indexes()

            segment = 0
            cursor = 1  # GitHub search API uses page (1-based)
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
                    segment = getattr(cp, "segment", 0)
                    cursor = max(1, cp.cursor)
                    processed_count = cp.processed_count
                    inserted_count = cp.inserted_count
                    duplicate_count = cp.duplicate_count
                    invalid_count = cp.invalid_count
                    failed_count = cp.failed_count
                    logger.info("products_ingestion_resuming", checkpoint=cp.to_dict())
            else:
                cp_repo.reset_checkpoint(self.VERTICAL, self.SOURCE)

            target = limit

            while processed_count < target:
                c_cnt = repo.count()
                current_db_count = c_cnt if isinstance(c_cnt, int) else 0
                if current_db_count >= target:
                    logger.info("products_target_reached_in_db", total=current_db_count, target=target)
                    break

                fetch_limit = min(batch_size, target - current_db_count)
                if fetch_limit <= 0:
                    fetch_limit = min(batch_size, target - processed_count)

                res = await adapter.discover_products(
                    limit=fetch_limit, segment=segment, page=cursor, return_tuple=True
                )
                if isinstance(res, tuple):
                    raw_products, next_segment, next_cursor, exhausted_all = res
                else:
                    raw_products = res
                    next_segment = segment
                    next_cursor = cursor + 1
                    exhausted_all = False

                if not raw_products and exhausted_all:
                    logger.info("products_all_sources_exhausted", segment=segment, page=cursor)
                    break

                segment = next_segment
                cursor = next_cursor

                if not raw_products:
                    continue

                discovered_total += len(raw_products)
                valid_items: list[tuple[Product, dict | None]] = []

                for raw in raw_products:
                    processed_count += 1
                    try:
                        collected_at = datetime.now(timezone.utc)
                        product = Product(
                            source={"name": raw.source_name, "url": raw.source_url},
                            content={
                                "startupName": raw.startup_name,
                                "pricingModel": raw.pricing_model,
                            },
                            collectedAt=collected_at,
                        )
                        provenance = {
                            "is_qualified": getattr(raw, "is_qualified", True),
                            "category": getattr(raw, "qualification_category", "APPLICATION_TOOL"),
                            "reasons": getattr(raw, "qualification_reasons", []),
                            "license": getattr(raw, "license_name", None),
                            "pricing_reasons": getattr(raw, "pricing_reasons", []),
                        }
                        valid_items.append((product, provenance))
                    except ValidationError as val_err:
                        invalid_count += 1
                        logger.warning("product_validation_failed", error=str(val_err), startup=raw.startup_name)
                    except Exception as exc:
                        failed_count += 1
                        logger.error("product_processing_failed", error=str(exc), startup=raw.startup_name)

                # Batch save
                b_inserted, b_duplicates = repo.save_batch(valid_items, dry_run=dry_run)
                inserted_count += b_inserted
                duplicate_count += b_duplicates

                # Update Checkpoint
                f_cnt = repo.count() if not dry_run else (current_db_count + inserted_count)
                final_db_count = f_cnt if isinstance(f_cnt, int) else (current_db_count + inserted_count)
                cp_status = "completed" if (final_db_count >= target or processed_count >= target) else "running"
                cp_repo.save_checkpoint(
                    Checkpoint(
                        vertical=self.VERTICAL,
                        source=self.SOURCE,
                        cursor=cursor,
                        segment=segment,
                        processed_count=processed_count,
                        inserted_count=inserted_count,
                        duplicate_count=duplicate_count,
                        invalid_count=invalid_count,
                        failed_count=failed_count,
                        last_successful_item=raw_products[-1].startup_name if raw_products else "",
                        status=cp_status,
                    )
                )

                if cp_status == "completed":
                    break

            duration = round(time.monotonic() - start_time, 2)
            throughput = round(processed_count / max(duration, 0.001), 2)
            f_cnt = repo.count()
            final_db_count = f_cnt if isinstance(f_cnt, int) else (current_db_count + inserted_count)
            final_status = "success" if (final_db_count >= target or processed_count >= target) else "partial"

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
                "db_total": final_db_count,
                "duration_seconds": duration,
                "throughput_per_sec": throughput,
                "dry_run": dry_run,
                "source_metrics": adapter.source_metrics,
            }

            logger.info("products_ingestion_completed", **result)
            return result

        except KeyboardInterrupt:
            logger.warning("products_ingestion_interrupted")
            cp_repo.save_checkpoint(
                Checkpoint(
                    vertical=self.VERTICAL,
                    source=self.SOURCE,
                    cursor=cursor if 'cursor' in locals() else 1,
                    segment=segment if 'segment' in locals() else 0,
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
            logger.error("products_ingestion_failed", error=str(exc))
            return {"status": "error", "count": 0, "error": str(exc)}
        finally:
            await adapter.close()
            repo.close()
            cp_repo.close()
