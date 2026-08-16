"""
AI Intelligence Pipeline - CLI Application

Unified command-line interface for all pipeline operations.
Thin orchestration layer — all business logic lives in src/services/.
"""

from __future__ import annotations

import sys
import asyncio

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.config.settings import get_settings
from src.utils.logging import setup_logging, get_logger
from src.cli.exit_codes import (
    EXIT_SUCCESS,
    EXIT_FAILURE,
    EXIT_VALIDATION_FAILURE,
    EXIT_SERVICE_FAILURE,
)

console = Console(force_terminal=True)


def _run_async(coro):
    """Run an async coroutine from a synchronous Click command."""
    return asyncio.run(coro)


# =====================================================================
# Root group
# =====================================================================


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """AI Intelligence Pipeline CLI

    Async crawling | LLM extraction | Entity resolution | MongoDB storage
    """
    settings = get_settings()
    setup_logging(settings.log_level)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings

    if ctx.invoked_subcommand is None:
        console.print(
            Panel.fit(
                "[bold cyan]>> AI Intelligence Pipeline[/bold cyan]\n"
                "[dim]Async crawling | LLM extraction | Entity resolution | MongoDB storage[/dim]",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )
        click.echo(ctx.get_help())


# =====================================================================
# health
# =====================================================================


@cli.command()
@click.pass_context
def health(ctx):
    """Check service configuration and connectivity."""
    from src.services.health import HealthService

    svc = HealthService(ctx.obj["settings"])
    result = svc.check()

    console.print()
    console.print(
        Panel.fit("[bold]AI Intelligence Pipeline Health[/bold]", border_style="bright_blue")
    )

    table = Table(show_header=False, border_style="dim", pad_edge=False)
    table.add_column("Service", style="cyan", min_width=18)
    table.add_column("Status", min_width=18)

    for chk in result["checks"]:
        if chk.get("connected") is True:
            status = "[green]Connected[/green]"
        elif chk.get("connected") is False:
            status = "[red]Not connected[/red]"
        elif chk["ok"]:
            status = "[green]Configured[/green]"
        else:
            status = "[yellow]Not configured[/yellow]"
        table.add_row(chk["name"], status)

    console.print(table)
    overall = "[bold green]READY[/bold green]" if result["healthy"] else "[bold yellow]DEGRADED[/bold yellow]"
    console.print(f"\nSystem status: {overall}\n")
    sys.exit(EXIT_SUCCESS if result["healthy"] else EXIT_SERVICE_FAILURE)


# =====================================================================
# test
# =====================================================================


@cli.command("test")
def run_tests():
    """Run automated tests."""
    import pytest

    logger = get_logger("cli.test")
    logger.info("running_tests")
    exit_code = pytest.main(["-v", "tests/"])
    sys.exit(exit_code)


# =====================================================================
# stats
# =====================================================================


@cli.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    from src.services.stats import StatsService

    svc = StatsService(ctx.obj["settings"])
    result = svc.get_stats()

    if result is None:
        console.print("[red]Failed to connect to MongoDB.[/red]")
        sys.exit(EXIT_SERVICE_FAILURE)

    console.print()
    console.print(Panel.fit("[bold]Database Statistics[/bold]", border_style="bright_blue"))

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Collection", style="cyan", min_width=22)
    table.add_column("Count", style="green", justify="right")

    for name, count in result["collections"].items():
        table.add_row(name.replace("_", " ").upper(), f"{count:,}")

    console.print(table)

    if result.get("quality"):
        console.print()
        qt = Table(title="Quality Metrics", show_header=True, header_style="bold magenta", border_style="dim")
        qt.add_column("Metric", style="cyan", min_width=32)
        qt.add_column("Value", style="green", justify="right")
        for metric, value in result["quality"].items():
            qt.add_row(metric.replace("_", " ").title(), f"{value:,}")
        console.print(qt)

    console.print()
    sys.exit(EXIT_SUCCESS)


# =====================================================================
# validate
# =====================================================================


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate data quality."""
    from src.services.validation import ValidationService

    svc = ValidationService(ctx.obj["settings"])
    result = svc.validate()
    report = result["report"]

    console.print()
    console.print(Panel.fit("[bold]Data Quality Validation[/bold]", border_style="bright_blue"))

    if "error" in report:
        console.print(f"[red]{report['error']}[/red]")
        sys.exit(EXIT_SERVICE_FAILURE)

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Check", style="cyan", min_width=28)
    table.add_column("Value", style="green", justify="right")

    for key, value in report.items():
        table.add_row(key.replace("_", " ").title(), f"{value:,}")

    console.print(table)

    if result["passed"]:
        console.print("\n[bold green]Validation PASSED[/bold green]\n")
    else:
        console.print("\n[bold red]Validation FAILED[/bold red]\n")

    sys.exit(EXIT_SUCCESS if result["passed"] else EXIT_VALIDATION_FAILURE)


# =====================================================================
# pipeline
# =====================================================================


@cli.command()
@click.option("--limit", default=10, help="Max records per source.", show_default=True)
@click.option("--workers", default=5, help="Concurrent workers.", show_default=True)
@click.option("--source", default=None, help="Run a single source only.")
@click.option("--skip-research", is_flag=True, help="Skip research papers.")
@click.option("--skip-startups", is_flag=True, help="Skip startups.")
@click.option("--skip-products", is_flag=True, help="Skip products.")
@click.option("--skip-news", is_flag=True, help="Skip news.")
@click.option("--skip-jobs", is_flag=True, help="Skip jobs.")
@click.pass_context
def pipeline(ctx, limit, workers, source, skip_research, skip_startups, skip_products, skip_news, skip_jobs):
    """Run complete ingestion pipeline."""
    from src.services.pipeline import PipelineService

    logger = get_logger("cli.pipeline")
    logger.info("pipeline_started", limit=limit, workers=workers)

    svc = PipelineService(ctx.obj["settings"])
    result = _run_async(svc.run(
        limit=limit, workers=workers, source=source,
        skip_research=skip_research, skip_startups=skip_startups,
        skip_products=skip_products, skip_news=skip_news, skip_jobs=skip_jobs,
    ))

    console.print()
    console.print(Panel.fit("[bold]Pipeline Results[/bold]", border_style="bright_blue"))

    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        sys.exit(EXIT_FAILURE)

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Stage", style="cyan", min_width=20)
    table.add_column("Status", min_width=18)
    table.add_column("Count", style="green", justify="right")

    for stage, info in result.get("stages", {}).items():
        status = info.get("status", "unknown")
        style = {"success": "green", "not_implemented": "yellow", "error": "red"}.get(status, "white")
        count = info.get("count", "-")
        if isinstance(info, dict) and "passed" in info:
            status = "passed" if info["passed"] else "failed"
            style = "green" if info["passed"] else "red"
            count = "-"
        table.add_row(stage.title(), f"[{style}]{status}[/{style}]", str(count))

    console.print(table)
    elapsed = result.get("elapsed_seconds", 0)
    console.print(f"\n[dim]Completed in {elapsed}s[/dim]\n")

    logger.info("pipeline_completed")
    sys.exit(EXIT_SUCCESS)


# =====================================================================
# Individual vertical commands
# =====================================================================


def _vertical_command(service_cls, name: str, help_text: str):
    """Factory for individual vertical CLI commands."""

    @cli.command(name, help=help_text)
    @click.option("--limit", default=10, help="Max records.", show_default=True)
    @click.option("--batch-size", default=50, help="Batch size for discovery & insert.", show_default=True)
    @click.option("--resume/--no-resume", default=True, help="Resume from last checkpoint.", show_default=True)
    @click.option("--dry-run", is_flag=True, help="Run discovery and validation without DB insertion.", show_default=True)
    @click.option("--workers", default=5, help="Concurrent workers.", show_default=True)
    @click.pass_context
    def cmd(ctx, limit, batch_size, resume, dry_run, workers):
        svc = service_cls(ctx.obj["settings"])
        result = _run_async(svc.ingest(
            limit=limit,
            batch_size=batch_size,
            resume=resume,
            dry_run=dry_run,
            workers=workers,
        ))
        status = result.get("status", "unknown")
        count = result.get("count", 0)
        msg = result.get("message", "")

        if status in ("completed", "partial", "success"):
            if "requested" in result:
                title_str = f"{name.title()} Ingestion ({status.upper()})"
                console.print()
                console.print(f"[bold cyan]{title_str}[/bold cyan]")
                console.print("=" * len(title_str))
                console.print(f"Source: [bold]{result.get('source', 'N/A')}[/bold]")
                console.print(f"Requested: {result.get('requested', limit)}")
                console.print(f"Discovered: {result.get('discovered', 0)}")
                console.print(f"Processed: {result.get('processed', 0)}")
                console.print(f"Valid: [green]{result.get('valid', 0)}[/green]")
                console.print(f"Inserted: [bold green]{result.get('inserted', 0)}[/bold green]")
                console.print(f"Duplicates: [yellow]{result.get('duplicates', 0)}[/yellow]")
                console.print(f"Invalid: [red]{result.get('invalid', 0)}[/red]")
                console.print(f"Failed: [red]{result.get('failed', 0)}[/red]")
                if "github_count" in result:
                    console.print(f"GitHub repositories: {result.get('github_count', 0)}")
                    console.print(f"GitHub stars retrieved: {result.get('github_stars_count', 0)}")
                console.print(f"Duration: {result.get('duration_seconds', 0)}s")
                console.print(f"Throughput: {result.get('throughput_per_sec', 0)} items/sec")
                if result.get("dry_run"):
                    console.print("[bold yellow]DRY RUN ONLY - No DB writes performed.[/bold yellow]")
                console.print()
                console.print("[bold green]Completed successfully.[/bold green]")
            else:
                console.print(f"[green]{name.title()} completed: {count} records[/green]")
        elif status == "not_implemented":
            console.print(f"[yellow]{name.title()}: {msg}[/yellow]")
        else:
            console.print(f"[red]{name.title()} failed: {result.get('error', 'unknown')}[/red]")
            sys.exit(EXIT_FAILURE)

    return cmd


# Register individual verticals
from src.services.research import ResearchService
from src.services.startups import StartupsService
from src.services.products import ProductsService
from src.services.news import NewsService
from src.services.jobs import JobsService

_vertical_command(ResearchService, "research", "Ingest research papers.")
_vertical_command(StartupsService, "startups", "Ingest startups.")
_vertical_command(ProductsService, "products", "Ingest products.")
_vertical_command(NewsService, "news", "Ingest fresh news.")
_vertical_command(JobsService, "jobs", "Ingest fresh jobs.")


# =====================================================================
# status (checkpoint overview) & reset-checkpoints
# =====================================================================


@cli.command("status")
@click.pass_context
def show_status(ctx):
    """Show ingestion checkpoints status across all verticals."""
    from src.storage.checkpoints import CheckpointRepository

    cp_repo = CheckpointRepository(settings=ctx.obj["settings"])
    checkpoints = cp_repo.get_all_checkpoints()

    console.print()
    console.print(Panel.fit("[bold]Ingestion Checkpoints Status[/bold]", border_style="bright_blue"))

    if not checkpoints:
        console.print("[yellow]No active checkpoints found.[/yellow]\n")
        sys.exit(EXIT_SUCCESS)

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Vertical", style="cyan", min_width=12)
    table.add_column("Source", style="cyan", min_width=16)
    table.add_column("Status", min_width=12)
    table.add_column("Cursor", justify="right")
    table.add_column("Processed", justify="right")
    table.add_column("Inserted", justify="right")
    table.add_column("Duplicates", justify="right")
    table.add_column("Last Item", min_width=20)

    for cp in checkpoints:
        st = cp.get("status", "unknown")
        style = {"completed": "green", "running": "cyan", "interrupted": "yellow"}.get(st, "white")
        table.add_row(
            cp.get("vertical", ""),
            cp.get("source", ""),
            f"[{style}]{st}[/{style}]",
            str(cp.get("cursor", 0)),
            f"{cp.get('processed_count', 0):,}",
            f"{cp.get('inserted_count', 0):,}",
            f"{cp.get('duplicate_count', 0):,}",
            cp.get("last_successful_item", "")[:25],
        )

    console.print(table)
    console.print()
    sys.exit(EXIT_SUCCESS)


@cli.command("reset-checkpoints")
@click.option("--vertical", default=None, help="Reset checkpoints for a specific vertical.")
@click.pass_context
def reset_checkpoints(ctx, vertical):
    """Reset ingestion checkpoints."""
    from src.storage.checkpoints import CheckpointRepository

    cp_repo = CheckpointRepository(settings=ctx.obj["settings"])
    count = cp_repo.reset_all(vertical=vertical)

    console.print(f"[green]Successfully reset {count} checkpoint(s).[/green]\n")
    sys.exit(EXIT_SUCCESS)


# =====================================================================
# resolve
# =====================================================================


@cli.command()
@click.pass_context
def resolve(ctx):
    """Run entity resolution pipeline across all entity sources."""
    from src.services.entity_resolution import EntityResolutionService

    svc = EntityResolutionService()
    res = svc.run_resolution_pipeline()

    console.print()
    console.print(Panel.fit("[bold]Entity Resolution[/bold]", border_style="bright_blue"))
    console.print()
    console.print(f"Processed:       {res.get('processed', 0)}")
    console.print(f"Exact:           {res.get('exact', 0)}")
    console.print(f"Normalized:      {res.get('normalized', 0)}")
    console.print(f"Alias:           {res.get('alias', 0)}")
    console.print(f"Fuzzy:           {res.get('fuzzy', 0)}")
    console.print(f"LLM:             {res.get('llm', 0)}")
    console.print(f"Unresolved:      {res.get('unresolved', 0)}")
    console.print()
    console.print(f"Canonical entities:\n{res.get('canonical_entities', 0)}")
    console.print()
    console.print(f"Mappings created:\n{res.get('mappings_created', 0)}")
    console.print()
    sys.exit(EXIT_SUCCESS)


# =====================================================================
# export
# =====================================================================


@cli.command()
@click.option("--dry-run", is_flag=True, help="Simulate export without writing to Google Sheets.")
@click.option(
    "--vertical",
    type=click.Choice(["research", "startups", "products", "news", "jobs", "entity-mappings", "entity_mappings", "entity-mapping-log"], case_sensitive=False),
    default=None,
    help="Filter export to a specific vertical or worksheet.",
)
@click.pass_context

def export(ctx, dry_run: bool, vertical: str | None):
    """Export validated pipeline data to Google Sheets."""
    from src.services.exporter import ExporterService

    svc = ExporterService(ctx.obj["settings"])
    result = svc.export(dry_run=dry_run, vertical=vertical)

    console.print()
    title_suffix = " (Dry Run)" if dry_run else ""
    console.print(
        Panel.fit(f"[bold]Google Sheets Export{title_suffix}[/bold]", border_style="bright_blue")
    )

    status = result.get("status", "unknown")
    if status in ("success", "dry_run"):
        table = Table(border_style="dim")
        table.add_column("Vertical / Sheet", style="cyan", min_width=18)
        table.add_column("Queried", justify="right")
        table.add_column("Valid", style="green", justify="right")
        table.add_column("Skipped", style="yellow", justify="right")
        table.add_column("Written", style="bold green", justify="right")
        table.add_column("Time (s)", justify="right")

        for key, val in result.items():
            if isinstance(val, dict) and "queried" in val:
                table.add_row(
                    val.get("vertical", key),
                    f"{val.get('queried', 0):,}",
                    f"{val.get('valid', 0):,}",
                    f"{val.get('skipped', 0):,}",
                    f"{val.get('written', 0):,}",
                    f"{val.get('elapsed_seconds', 0.0):.2f}",
                )
        console.print(table)
        total_w = result.get("total_written", 0)
        total_t = result.get("total_elapsed_seconds", 0.0)
        mode_str = "SIMULATED EXPORT (DRY RUN)" if dry_run else "SUCCESS"
        console.print(f"\nSpreadsheet: {result.get('spreadsheet_id') or 'N/A'}")
        console.print(f"Total Written: [bold green]{total_w:,}[/bold green] rows in {total_t:.2f}s")
        console.print(f"Status: [bold green]{mode_str}[/bold green]\n")
    elif status == "not_configured":
        console.print(f"[yellow]{result.get('message', 'Google Sheets not configured.')}[/yellow]\n")
    else:
        console.print(f"[red]Export failed: {result.get('error', 'unknown')}[/red]\n")
        sys.exit(EXIT_FAILURE)

    sys.exit(EXIT_SUCCESS)


# =====================================================================
# benchmark
# =====================================================================


@cli.command()
@click.option("--records", default=100, help="Number of test records.", show_default=True)
@click.option("--workers", default=5, help="Concurrent workers.", show_default=True)
@click.pass_context
def benchmark(ctx, records, workers):
    """Run performance benchmark."""
    from src.services.benchmark import BenchmarkService

    svc = BenchmarkService(ctx.obj["settings"])
    result = svc.run(records=records, workers=workers)

    console.print()
    console.print(Panel.fit("[bold]AI Intelligence Pipeline Benchmark[/bold]", border_style="bright_blue"))

    table = Table(show_header=False, border_style="dim")
    table.add_column("Metric", style="cyan", min_width=24)
    table.add_column("Value", style="green", justify="right")

    table.add_row("Records", f"{result.records:,}")
    table.add_row("Workers", str(result.workers))
    table.add_row("Execution time", f"{result.elapsed_seconds} sec")
    table.add_row("Throughput", f"{result.throughput} records/sec")
    table.add_row("Successful", f"{result.successful:,}")
    table.add_row("Failed", f"{result.failed:,}")
    table.add_row("Retries", str(result.retries))
    table.add_row("Avg response time", f"{result.avg_response_ms} ms")
    if result.memory_mb:
        table.add_row("Memory delta", f"{result.memory_mb} MB")

    console.print(table)
    console.print()
    sys.exit(EXIT_SUCCESS)


# =====================================================================
# crawl-test
# =====================================================================


@cli.command("crawl-test")
@click.option("--url", default="https://example.com", help="URL to fetch.", show_default=True)
@click.pass_context
def crawl_test(ctx, url):
    """Test the async crawler engine against a single URL."""
    from src.services.crawl_test import CrawlTestService

    svc = CrawlTestService(ctx.obj["settings"])
    result = _run_async(svc.run(url=url))

    console.print()
    console.print(Panel.fit("[bold]Crawler Test[/bold]", border_style="bright_blue"))

    table = Table(show_header=False, border_style="dim")
    table.add_column("Metric", style="cyan", min_width=20)
    table.add_column("Value", style="green", justify="right")

    table.add_row("URL", result.url)
    table.add_row("Status", str(result.status_code or "N/A"))
    table.add_row("Response time", f"{result.response_time}s")
    table.add_row("Attempts", str(result.attempts))
    table.add_row("Content length", f"{result.content_length:,}")
    table.add_row(
        "Success",
        "[green]True[/green]" if result.success else "[red]False[/red]",
    )
    if result.error:
        table.add_row("Error", f"[red]{result.error}[/red]")

    console.print(table)
    console.print()
    sys.exit(EXIT_SUCCESS if result.success else EXIT_FAILURE)


# =====================================================================
# llm-health & llm-smoke-test
# =====================================================================


@cli.command("llm-health")
@click.pass_context
def llm_health(ctx):
    """Report LLM provider configuration status without inference."""
    from src.llm import LLMOrchestrator

    orchestrator = LLMOrchestrator()
    status_dict = orchestrator.get_health_status()

    console.print()
    console.print(Panel.fit("[bold]LLM Provider Health[/bold]", border_style="bright_blue"))

    table = Table(show_header=False, border_style="dim")
    table.add_column("Provider", style="cyan", min_width=18)
    table.add_column("Status", min_width=18)

    for provider_name, status_str in status_dict.items():
        if status_str == "Configured":
            style_status = "[green]Configured[/green]"
        else:
            style_status = "[yellow]Not configured[/yellow]"
        table.add_row(provider_name, style_status)

    console.print(table)
    console.print()
    sys.exit(EXIT_SUCCESS)


@cli.command("llm-smoke-test")
@click.pass_context
def llm_smoke_test(ctx):
    """Run minimal optional smoke test against configured LLM providers."""
    from src.llm import (
        OpenRouterProvider,
        GeminiProvider,
        GroqProvider,
        DeepSeekProvider,
        LLMOrchestrator,
    )
    from pydantic import BaseModel

    class SmokeTestSchema(BaseModel):
        status: str
        message: str = "ok"

    providers = [
        OpenRouterProvider(),
        GeminiProvider(),
        GroqProvider(),
        DeepSeekProvider(),
    ]

    console.print()
    console.print(Panel.fit("[bold]LLM Provider Smoke Test[/bold]", border_style="bright_blue"))

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Provider", style="cyan", min_width=12)
    table.add_column("Status", min_width=10)
    table.add_column("Requested Model", min_width=18)
    table.add_column("Actual Model", min_width=24)
    table.add_column("Latency", justify="right")
    table.add_column("Valid Output", min_width=12)

    for p in providers:
        if not p.is_configured():
            table.add_row(
                p.name.capitalize(),
                "[yellow]SKIPPED[/yellow]",
                p.model,
                "-",
                "-",
                "-",
            )
            continue

        orch = LLMOrchestrator(providers=[p], max_retries=1)
        try:
            res = _run_async(orch.extract_structured(
                prompt='Return JSON: {"status": "ok", "message": "hello"}',
                target_schema=SmokeTestSchema,
                system_prompt="Return JSON only.",
            ))
            latency = orch.telemetry.get_records()[-1].latency if orch.telemetry.get_records() else 0.0
            actual_model = getattr(res, "model", p.model) if hasattr(res, "model") else p.model
            table.add_row(
                p.name.capitalize(),
                "[green]SUCCESS[/green]",
                p.model,
                str(actual_model),
                f"{latency:.2f}s",
                "[green]True[/green]",
            )
        except Exception as exc:
            table.add_row(
                p.name.capitalize(),
                "[red]FAILED[/red]",
                p.model,
                "-",
                "-",
                "[red]False[/red]",
            )

    console.print(table)
    console.print()
    sys.exit(EXIT_SUCCESS)


# =====================================================================
# Entry point
# =====================================================================


def main():
    cli(obj={})

