"""Google Sheets Exporter Orchestrator.

Queries MongoDB for canonical pipeline records, transforms and validates them,
and executes idempotent batch writes to Google Sheets.
"""

from __future__ import annotations

import time
from typing import Any
from pymongo import MongoClient

from src.config.settings import Settings, get_settings
from src.integrations.google_sheets.client import (
    GoogleSheetsClient,
    classify_google_error,
    redact_credentials,
)
from src.integrations.google_sheets.models import (
    ExportOptions,
    ExportSummary,
    VerticalTelemetry,
)
from src.integrations.google_sheets.transformers import VERTICAL_TRANSFORMERS
from src.utils.logging import get_logger

logger = get_logger(__name__)

MONGO_COLLECTIONS = {
    "research": "research_papers",
    "startups": "startups",
    "products": "products",
    "news": "news",
    "jobs": "jobs",
    "entity-mappings": "entity_mappings",
    "entity_mappings": "entity_mappings",
    "entity-mapping-log": "entity_mappings",
    "entity_mapping_log": "entity_mappings",
}

VERTICAL_ALIAS_MAP = {
    "research": "research",
    "startups": "startups",
    "products": "products",
    "news": "news",
    "jobs": "jobs",
    "entity-mappings": "entity-mappings",
    "entity_mappings": "entity-mappings",
    "entity-mapping-log": "entity-mappings",
    "entity_mapping_log": "entity-mappings",
}


class GoogleSheetsExporter:
    """Orchestrates reading MongoDB records, validating, and writing to Google Sheets."""

    def __init__(
        self,
        settings: Settings | None = None,
        mongo_client: MongoClient | None = None,
        sheets_client: GoogleSheetsClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._mongo_client = mongo_client
        self._sheets_client = sheets_client

    def _get_mongo_db(self):
        if self._mongo_client is None:
            self._mongo_client = MongoClient(
                self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
            )
        return self._mongo_client[self.settings.mongodb_database]

    def _get_sheets_client(self, options: ExportOptions) -> GoogleSheetsClient:
        if self._sheets_client is None:
            json_str = options.service_account_json or self.settings.google_service_account_json
            file_path = (
                options.service_account_file
                or self.settings.google_service_account_file
                or self.settings.google_sheets_credentials_file
            )
            self._sheets_client = GoogleSheetsClient(
                service_account_json=json_str,
                service_account_file=file_path,
            )
        return self._sheets_client

    def export(self, options: ExportOptions | None = None) -> ExportSummary:
        """Run export according to provided options.

        Supports single vertical filtering or all 6 worksheets.
        Supports --dry-run.
        """
        start_time = time.time()
        opts = options or ExportOptions(
            spreadsheet_id=self.settings.google_sheets_spreadsheet_id,
            service_account_json=self.settings.google_service_account_json,
            service_account_file=self.settings.google_service_account_file,
            batch_size=self.settings.google_sheets_batch_size,
        )

        spreadsheet_id = opts.spreadsheet_id or self.settings.google_sheets_spreadsheet_id

        # Determine target verticals
        if opts.vertical:
            raw_key = opts.vertical.lower()
            vert_key = VERTICAL_ALIAS_MAP.get(raw_key, raw_key)
            if vert_key not in VERTICAL_TRANSFORMERS:
                return ExportSummary(
                    status="error",
                    spreadsheet_id=spreadsheet_id,
                    error=f"Invalid vertical: {opts.vertical}. Choices: {list(VERTICAL_TRANSFORMERS.keys())}",
                )
            target_verticals = [vert_key]
        else:
            target_verticals = list(VERTICAL_TRANSFORMERS.keys())


        # Check configuration for non-dry-run
        if not opts.dry_run:
            if not self.settings.google_sheets_enabled and not opts.spreadsheet_id:
                logger.warning("export_google_sheets_disabled")
                return ExportSummary(
                    status="not_configured",
                    spreadsheet_id=spreadsheet_id,
                    message="Google Sheets export is disabled. Set GOOGLE_SHEETS_ENABLED=true and configure GOOGLE_SHEETS_SPREADSHEET_ID.",
                )
            if not spreadsheet_id:
                return ExportSummary(
                    status="not_configured",
                    spreadsheet_id=spreadsheet_id,
                    message="GOOGLE_SHEETS_SPREADSHEET_ID is missing.",
                )

        summary = ExportSummary(
            status="dry_run" if opts.dry_run else "success",
            spreadsheet_id=spreadsheet_id,
        )

        db = self._get_mongo_db()

        # Connect & verify Google Sheets if not dry_run
        sheets_client = None
        if not opts.dry_run:
            try:
                sheets_client = self._get_sheets_client(opts)
                connected, conn_msg = sheets_client.verify_connection(spreadsheet_id)
                if not connected:
                    logger.error("google_sheets_connection_failed", error=conn_msg)
                    summary.status = "error"
                    summary.error = f"Google Sheets connection failed: {conn_msg}"
                    return summary
            except Exception as exc:
                diagnostic = classify_google_error(exc)
                logger.error("google_sheets_auth_failed", error=diagnostic)
                summary.status = "error"
                summary.error = f"Google Sheets authentication error: {diagnostic}"
                return summary

        total_written = 0

        for vert in target_verticals:
            vert_start = time.time()
            sheet_title, headers, transform_fn = VERTICAL_TRANSFORMERS[vert]
            coll_name = MONGO_COLLECTIONS[vert]

            collection = db[coll_name]
            cursor = collection.find({})

            queried = 0
            valid_rows: list[list[Any]] = []
            invalid = 0
            skipped = 0

            for doc in cursor:
                queried += 1
                row = transform_fn(doc)
                if row is not None:
                    valid_rows.append(row)
                else:
                    invalid += 1
                    skipped += 1

            written = 0
            if not opts.dry_run and sheets_client:
                written = sheets_client.clear_and_write_worksheet(
                    spreadsheet_id=spreadsheet_id,
                    title=sheet_title,
                    headers=headers,
                    rows=valid_rows,
                    batch_size=opts.batch_size,
                )
            else:
                # Dry run counts valid rows as what would be written
                written = len(valid_rows)

            vert_elapsed = time.time() - vert_start
            telem = VerticalTelemetry(
                vertical=sheet_title,
                queried=queried,
                valid=len(valid_rows),
                invalid=invalid,
                skipped=skipped,
                written=written,
                elapsed_seconds=vert_elapsed,
            )
            summary.verticals[sheet_title] = telem
            total_written += written

        summary.total_written = total_written
        summary.total_elapsed_seconds = time.time() - start_time
        return summary
