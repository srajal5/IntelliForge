"""Test GoogleSheetsExporter orchestrator logic with mocked MongoDB and Google API."""

from unittest.mock import MagicMock, patch
from src.integrations.google_sheets import ExportOptions, GoogleSheetsExporter


def test_exporter_dry_run():
    mock_mongo = MagicMock()
    mock_db = MagicMock()
    mock_mongo.__getitem__.return_value = mock_db

    col_research = MagicMock()
    col_research.find.return_value = [{"content": {"title": "P1", "paper_url": "http://arxiv.org/1"}}]
    col_startups = MagicMock()
    col_startups.find.return_value = [{"content": {"entityName": "S1"}}]
    col_products = MagicMock()
    col_products.find.return_value = [{"provenance": {"product_name": "Pr1"}}]
    col_news = MagicMock()
    col_news.find.return_value = [{"content": {"title": "N1", "url": "http://news/1"}}]
    col_jobs = MagicMock()
    col_jobs.find.return_value = [{"content": {"company": "J1", "date": "2026-08-01"}}]

    def get_coll(name):
        return {
            "research_papers": col_research,
            "startups": col_startups,
            "products": col_products,
            "news": col_news,
            "jobs": col_jobs,
        }.get(name, MagicMock())

    mock_db.__getitem__.side_effect = get_coll

    exporter = GoogleSheetsExporter(mongo_client=mock_mongo)
    options = ExportOptions(dry_run=True, spreadsheet_id="test_sheet_id")

    summary = exporter.export(options)
    assert summary.status == "dry_run"
    assert summary.total_written == 5
    assert "Research Papers" in summary.verticals
    assert summary.verticals["Research Papers"].valid == 1


def test_exporter_vertical_filter():
    mock_mongo = MagicMock()
    mock_db = MagicMock()
    mock_mongo.__getitem__.return_value = mock_db

    mock_coll = MagicMock()
    mock_coll.find.return_value = [
        {
            "content": {
                "company": "Test Co",
                "date": "2026-08-01",
                "is_remote": True,
            }
        }
    ]
    mock_db.__getitem__.return_value = mock_coll

    exporter = GoogleSheetsExporter(mongo_client=mock_mongo)
    options = ExportOptions(dry_run=True, vertical="jobs", spreadsheet_id="test_sheet_id")

    summary = exporter.export(options)
    assert summary.status == "dry_run"
    assert summary.total_written == 1
    assert list(summary.verticals.keys()) == ["Jobs"]
    assert summary.verticals["Jobs"].valid == 1


def test_exporter_invalid_vertical():
    exporter = GoogleSheetsExporter()
    options = ExportOptions(dry_run=True, vertical="invalid_name")

    summary = exporter.export(options)
    assert summary.status == "error"
    assert "Invalid vertical" in (summary.error or "")


def test_exporter_connection_error():
    mock_mongo = MagicMock()
    mock_sheets_client = MagicMock()
    mock_sheets_client.verify_connection.return_value = (False, "Permission Denied")

    exporter = GoogleSheetsExporter(mongo_client=mock_mongo, sheets_client=mock_sheets_client)
    options = ExportOptions(dry_run=False, spreadsheet_id="test_sheet_id")

    summary = exporter.export(options)
    assert summary.status == "error"
    assert "Google Sheets connection failed" in (summary.error or "")
