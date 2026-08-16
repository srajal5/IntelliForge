"""Test CLI export command options and behavior."""

from click.testing import CliRunner
from unittest.mock import patch
from src.cli.app import cli


def test_cli_export_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output
    assert "--vertical" in result.output


def test_cli_export_dry_run_all():
    runner = CliRunner()

    mock_summary = {
        "status": "dry_run",
        "spreadsheet_id": "test_sheet_123",
        "total_written": 50,
        "total_elapsed_seconds": 0.12,
        "Research Papers": {"vertical": "Research Papers", "queried": 10, "valid": 10, "skipped": 0, "written": 10, "elapsed_seconds": 0.02},
        "Startups": {"vertical": "Startups", "queried": 10, "valid": 10, "skipped": 0, "written": 10, "elapsed_seconds": 0.02},
        "Products": {"vertical": "Products", "queried": 10, "valid": 10, "skipped": 0, "written": 10, "elapsed_seconds": 0.02},
        "News": {"vertical": "News", "queried": 10, "valid": 10, "skipped": 0, "written": 10, "elapsed_seconds": 0.02},
        "Jobs": {"vertical": "Jobs", "queried": 10, "valid": 10, "skipped": 0, "written": 10, "elapsed_seconds": 0.02},
    }

    with patch("src.services.exporter.ExporterService.export", return_value=mock_summary):
        result = runner.invoke(cli, ["export", "--dry-run"])
        assert result.exit_code == 0
        assert "Google Sheets Export (Dry Run)" in result.output
        assert "Research Papers" in result.output
        assert "SIMULATED EXPORT" in result.output
        assert "DRY RUN" in result.output


def test_cli_export_dry_run_vertical():
    runner = CliRunner()

    mock_summary = {
        "status": "dry_run",
        "spreadsheet_id": "test_sheet_123",
        "total_written": 10,
        "total_elapsed_seconds": 0.02,
        "Research Papers": {"vertical": "Research Papers", "queried": 10, "valid": 10, "skipped": 0, "written": 10, "elapsed_seconds": 0.02},
    }

    with patch("src.services.exporter.ExporterService.export", return_value=mock_summary):
        result = runner.invoke(cli, ["export", "--dry-run", "--vertical", "research"])
        assert result.exit_code == 0
        assert "Research Papers" in result.output


def test_cli_export_not_configured():
    runner = CliRunner()

    mock_summary = {
        "status": "not_configured",
        "message": "Google Sheets export is disabled.",
    }

    with patch("src.services.exporter.ExporterService.export", return_value=mock_summary):
        result = runner.invoke(cli, ["export"])
        assert result.exit_code == 0
        assert "Google Sheets export is disabled" in result.output
