"""Test Google Sheets configuration and environment variables."""

from src.config.settings import Settings


def test_google_sheets_settings_defaults():
    settings = Settings()
    assert hasattr(settings, "google_sheets_enabled")
    assert hasattr(settings, "google_sheets_spreadsheet_id")
    assert hasattr(settings, "google_service_account_json")
    assert hasattr(settings, "google_service_account_file")
    assert hasattr(settings, "google_sheets_batch_size")
    assert settings.google_sheets_batch_size == 500


def test_google_sheets_settings_env_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "test_sheet_123")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}')
    monkeypatch.setenv("GOOGLE_SHEETS_BATCH_SIZE", "250")

    settings = Settings()
    assert settings.google_sheets_enabled is True
    assert settings.google_sheets_spreadsheet_id == "test_sheet_123"
    assert settings.google_service_account_json == '{"type": "service_account"}'
    assert settings.google_sheets_batch_size == 250
