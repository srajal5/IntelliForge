"""
Application settings loaded from environment variables.

Uses pydantic-settings style validation with python-dotenv for .env loading.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Load .env from project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=_ENV_PATH)


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration sourced from environment variables."""

    # --- MongoDB ---
    mongodb_uri: str = field(
        default_factory=lambda: os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    )
    mongodb_database: str = field(
        default_factory=lambda: os.getenv("MONGODB_DATABASE", "ai_intelligence_pipeline")
    )

    # --- LLM API Keys & Settings ---
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    )
    groq_api_key: str = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY", "")
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "")
    )
    deepseek_model: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    )

    # --- OpenRouter ---
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )
    openrouter_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openrouter/free")
    )
    openrouter_base_url: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    )
    openrouter_daily_request_limit: int = field(
        default_factory=lambda: int(os.getenv("OPENROUTER_DAILY_REQUEST_LIMIT", "50"))
    )
    openrouter_rpm_limit: int = field(
        default_factory=lambda: int(os.getenv("OPENROUTER_RPM_LIMIT", "20"))
    )

    # --- LLM Provider Selection ---
    llm_primary_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PRIMARY_PROVIDER", "openrouter")
    )
    llm_fallback_providers: str = field(
        default_factory=lambda: os.getenv("LLM_FALLBACK_PROVIDERS", "gemini,groq,deepseek")
    )

    # --- LLM Orchestrator Config ---
    llm_max_retries: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "3"))
    )
    llm_backoff_base: float = field(
        default_factory=lambda: float(os.getenv("LLM_BACKOFF_BASE", "2.0"))
    )
    llm_backoff_max: float = field(
        default_factory=lambda: float(os.getenv("LLM_BACKOFF_MAX", "30.0"))
    )
    llm_concurrency: int = field(
        default_factory=lambda: int(os.getenv("LLM_CONCURRENCY", "5"))
    )
    llm_max_input_chars: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_INPUT_CHARS", "12000"))
    )

    # --- GitHub ---
    github_token: str = field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN", "")
    )

    # --- Google Sheets ---
    google_sheets_enabled: bool = field(
        default_factory=lambda: os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() in ("true", "1", "yes")
    )
    google_sheets_spreadsheet_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    )
    google_service_account_json: str = field(
        default_factory=lambda: os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    )
    google_service_account_file: str = field(
        default_factory=lambda: os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE",
            os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", ""),
        )
    )
    google_sheets_credentials_file: str = field(
        default_factory=lambda: os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")
    )
    google_sheets_batch_size: int = field(
        default_factory=lambda: int(os.getenv("GOOGLE_SHEETS_BATCH_SIZE", "500"))
    )

    # --- Application ---
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    max_concurrent_crawlers: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_CRAWLERS", "5"))
    )
    retry_max_attempts: int = field(
        default_factory=lambda: int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    )
    retry_delay_seconds: float = field(
        default_factory=lambda: float(os.getenv("RETRY_DELAY_SECONDS", "2"))
    )

    # --- Crawler Engine ---
    crawler_concurrency: int = field(
        default_factory=lambda: int(os.getenv("CRAWLER_CONCURRENCY", "10"))
    )
    crawler_timeout: int = field(
        default_factory=lambda: int(os.getenv("CRAWLER_TIMEOUT", "30"))
    )
    crawler_max_retries: int = field(
        default_factory=lambda: int(os.getenv("CRAWLER_MAX_RETRIES", "3"))
    )
    crawler_backoff_base: float = field(
        default_factory=lambda: float(os.getenv("CRAWLER_BACKOFF_BASE", "2.0"))
    )
    crawler_backoff_max: float = field(
        default_factory=lambda: float(os.getenv("CRAWLER_BACKOFF_MAX", "60.0"))
    )
    crawler_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "CRAWLER_USER_AGENT",
            "AIIntelligencePipeline/1.0 (+https://github.com/ai-intelligence-pipeline; research)",
        )
    )

    # --- Multi-Source Configurations ---
    news_sources: str = field(
        default_factory=lambda: os.getenv(
            "NEWS_SOURCES",
            "techcrunch,venturebeat,mit_tech_review,hackernews,kdnuggets,devto,huggingface,arxiv",
        )
    )
    jobs_sources: str = field(
        default_factory=lambda: os.getenv(
            "JOBS_SOURCES", "arbeitnow,remoteok,jobicy,weworkremotely,himalayas"
        )
    )
    startup_sources: str = field(
        default_factory=lambda: os.getenv("STARTUP_SOURCES", "github_orgs")
    )
    product_sources: str = field(
        default_factory=lambda: os.getenv("PRODUCT_SOURCES", "github_repos")
    )

    # --- Derived ---
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
