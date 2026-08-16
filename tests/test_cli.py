"""Tests for the CLI commands.

All external services (MongoDB, LLM APIs, Google Sheets, GitHub) are mocked.
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock
from click.testing import CliRunner

from src.cli.app import cli


runner = CliRunner()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _async_return(value):
    """Create an AsyncMock that returns *value* when awaited."""
    mock = AsyncMock(return_value=value)
    return mock


# ------------------------------------------------------------------
# --help
# ------------------------------------------------------------------


def test_help_shows_all_commands():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "health", "test", "stats", "validate", "pipeline",
        "research", "startups", "products", "news", "jobs",
        "resolve", "export", "benchmark",
    ):
        assert cmd in result.output


def test_pipeline_help():
    result = runner.invoke(cli, ["pipeline", "--help"])
    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "--workers" in result.output
    assert "--skip-research" in result.output


# ------------------------------------------------------------------
# health
# ------------------------------------------------------------------


@patch("src.services.health.HealthService.check")
def test_health_ready(mock_check):
    mock_check.return_value = {
        "healthy": True,
        "checks": [
            {"name": "MongoDB", "ok": True, "connected": True, "required": True},
            {"name": "Gemini", "ok": True, "required": False},
        ],
    }
    result = runner.invoke(cli, ["health"])
    assert result.exit_code == 0
    assert "READY" in result.output


@patch("src.services.health.HealthService.check")
def test_health_degraded(mock_check):
    mock_check.return_value = {
        "healthy": False,
        "checks": [
            {"name": "MongoDB", "ok": False, "connected": False, "required": True},
        ],
    }
    result = runner.invoke(cli, ["health"])
    assert result.exit_code == 5  # EXIT_SERVICE_FAILURE
    assert "DEGRADED" in result.output


# ------------------------------------------------------------------
# stats
# ------------------------------------------------------------------


@patch("src.services.stats.StatsService.get_stats")
def test_stats_success(mock_stats):
    mock_stats.return_value = {
        "collections": {
            "startups": 10, "products": 5, "research_papers": 3,
            "jobs": 2, "news": 1, "entity_mappings": 0,
        },
        "quality": {"duplicate_records": 1, "missing_source_urls": 0},
    }
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0
    assert "STARTUPS" in result.output


@patch("src.services.stats.StatsService.get_stats")
def test_stats_no_connection(mock_stats):
    mock_stats.return_value = None
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 5


# ------------------------------------------------------------------
# validate
# ------------------------------------------------------------------


@patch("src.services.validation.ValidationService.validate")
def test_validate_pass(mock_validate):
    mock_validate.return_value = {
        "passed": True,
        "report": {"startups": 10, "invalid_records": 0, "llm_failures": 0},
    }
    result = runner.invoke(cli, ["validate"])
    assert result.exit_code == 0
    assert "PASSED" in result.output


@patch("src.services.validation.ValidationService.validate")
def test_validate_fail(mock_validate):
    mock_validate.return_value = {
        "passed": False,
        "report": {"startups": 10, "invalid_records": 3, "llm_failures": 1},
    }
    result = runner.invoke(cli, ["validate"])
    assert result.exit_code == 4  # EXIT_VALIDATION_FAILURE
    assert "FAILED" in result.output


# ------------------------------------------------------------------
# pipeline
# ------------------------------------------------------------------


@patch("src.services.pipeline.PipelineService.run", new_callable=AsyncMock)
def test_pipeline_success(mock_run):
    mock_run.return_value = {
        "stages": {"research": {"status": "not_implemented", "count": 0}},
        "elapsed_seconds": 0.5,
    }
    result = runner.invoke(cli, ["pipeline", "--limit", "5"])
    assert result.exit_code == 0
    assert "Research" in result.output


# ------------------------------------------------------------------
# individual verticals
# ------------------------------------------------------------------


@patch("src.services.research.ResearchService.ingest", new_callable=AsyncMock)
def test_research_not_implemented(mock_ingest):
    mock_ingest.return_value = {
        "status": "not_implemented", "count": 0, "message": "Not yet implemented",
    }
    result = runner.invoke(cli, ["research", "--limit", "5"])
    assert result.exit_code == 0


@patch("src.services.research.ResearchService.ingest", new_callable=AsyncMock)
def test_research_success(mock_ingest):
    mock_ingest.return_value = {
        "status": "success",
        "source": "arXiv",
        "requested": 5,
        "discovered": 5,
        "valid": 5,
        "inserted": 5,
        "duplicates": 0,
        "invalid": 0,
        "github_count": 2,
        "github_stars_count": 2,
        "count": 5,
    }
    result = runner.invoke(cli, ["research", "--limit", "5"])
    assert result.exit_code == 0
    assert "Research Ingestion" in result.output
    assert "Completed successfully" in result.output


@patch("src.services.startups.StartupsService.ingest", new_callable=AsyncMock)
def test_startups_not_implemented(mock_ingest):
    mock_ingest.return_value = {
        "status": "not_implemented", "count": 0, "message": "Not yet implemented",
    }
    result = runner.invoke(cli, ["startups"])
    assert result.exit_code == 0


@patch("src.services.startups.StartupsService.ingest", new_callable=AsyncMock)
def test_startups_success(mock_ingest):
    mock_ingest.return_value = {
        "status": "success",
        "source": "GitHub Organizations",
        "requested": 5,
        "discovered": 5,
        "valid": 5,
        "inserted": 5,
        "duplicates": 0,
        "invalid": 0,
        "count": 5,
    }
    result = runner.invoke(cli, ["startups", "--limit", "5"])
    assert result.exit_code == 0
    assert "Startups Ingestion" in result.output
    assert "Completed successfully" in result.output


@patch("src.services.products.ProductsService.ingest", new_callable=AsyncMock)
def test_products_not_implemented(mock_ingest):
    mock_ingest.return_value = {
        "status": "not_implemented", "count": 0, "message": "Not yet implemented",
    }
    result = runner.invoke(cli, ["products"])
    assert result.exit_code == 0


@patch("src.services.products.ProductsService.ingest", new_callable=AsyncMock)
def test_products_success(mock_ingest):
    mock_ingest.return_value = {
        "status": "success",
        "source": "GitHub Products",
        "requested": 5,
        "discovered": 5,
        "valid": 5,
        "inserted": 5,
        "duplicates": 0,
        "invalid": 0,
        "count": 5,
    }
    result = runner.invoke(cli, ["products", "--limit", "5"])
    assert result.exit_code == 0
    assert "Products Ingestion" in result.output
    assert "Completed successfully" in result.output


@patch("src.services.news.NewsService.ingest", new_callable=AsyncMock)
def test_news_not_implemented(mock_ingest):
    mock_ingest.return_value = {
        "status": "not_implemented", "count": 0, "message": "Not yet implemented",
    }
    result = runner.invoke(cli, ["news"])
    assert result.exit_code == 0


@patch("src.services.jobs.JobsService.ingest", new_callable=AsyncMock)
def test_jobs_not_implemented(mock_ingest):
    mock_ingest.return_value = {
        "status": "not_implemented", "count": 0, "message": "Not yet implemented",
    }
    result = runner.invoke(cli, ["jobs"])
    assert result.exit_code == 0


# ------------------------------------------------------------------
# resolve
# ------------------------------------------------------------------


@patch("src.services.entity_resolution.EntityResolutionService.run_resolution_pipeline")
def test_resolve(mock_run_pipeline):
    mock_run_pipeline.return_value = {
        "processed": 20,
        "exact": 5,
        "normalized": 6,
        "alias": 4,
        "fuzzy": 3,
        "llm": 0,
        "unresolved": 2,
        "canonical_entities": 10,
        "mappings_created": 20,
    }
    result = runner.invoke(cli, ["resolve"])
    assert result.exit_code == 0
    assert "Entity Resolution" in result.output
    assert "Processed:" in result.output
    assert "20" in result.output


# ------------------------------------------------------------------
# export
# ------------------------------------------------------------------


@patch("src.services.exporter.ExporterService.export")
def test_export_not_configured(mock_export):
    mock_export.return_value = {
        "status": "not_configured", "message": "Spreadsheet ID not set",
    }
    result = runner.invoke(cli, ["export"])
    assert result.exit_code == 0


# ------------------------------------------------------------------
# benchmark
# ------------------------------------------------------------------


@patch("src.services.benchmark.BenchmarkService.run")
def test_benchmark(mock_run):
    from src.services.benchmark import BenchmarkResult

    mock_run.return_value = BenchmarkResult(
        records=50, workers=5, elapsed_seconds=1.5,
        throughput=33.33, successful=50, failed=0,
    )
    result = runner.invoke(cli, ["benchmark", "--records", "50"])
    assert result.exit_code == 0
    assert "50" in result.output
