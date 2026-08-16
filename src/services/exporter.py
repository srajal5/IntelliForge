"""Google Sheets export service."""

from __future__ import annotations

from src.config.settings import Settings
from src.integrations.google_sheets import ExportOptions, GoogleSheetsExporter
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ExporterService:
    """Service wrapper for Google Sheets export operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.exporter = GoogleSheetsExporter(settings=settings)

    def export(
        self,
        dry_run: bool = False,
        vertical: str | None = None,
        spreadsheet_id: str | None = None,
    ) -> dict:
        """Export collections to Google Sheets. Returns summary dict."""
        logger.info("export_started", dry_run=dry_run, vertical=vertical)

        options = ExportOptions(
            spreadsheet_id=spreadsheet_id or self.settings.google_sheets_spreadsheet_id,
            service_account_json=self.settings.google_service_account_json,
            service_account_file=self.settings.google_service_account_file,
            batch_size=self.settings.google_sheets_batch_size,
            dry_run=dry_run,
            vertical=vertical,
        )

        summary = self.exporter.export(options)
        result_dict = summary.to_dict()
        logger.info("export_finished", status=summary.status, total_written=summary.total_written)
        return result_dict
