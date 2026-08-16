"""Smoke tests to verify the project foundation is working."""

from src.config.settings import Settings, get_settings
from src.utils.logging import setup_logging, get_logger


def test_settings_defaults():
    """Settings should instantiate with sensible defaults."""
    settings = Settings()
    assert settings.mongodb_database == "ai_intelligence_pipeline"
    assert settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    assert settings.max_concurrent_crawlers > 0
    assert settings.retry_max_attempts > 0


def test_get_settings_singleton():
    """get_settings should return the same cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_setup_logging_runs():
    """setup_logging should execute without errors."""
    setup_logging("DEBUG")
    logger = get_logger("test")
    assert logger is not None
