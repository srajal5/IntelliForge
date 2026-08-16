"""Test GoogleSheetsClient authentication, retries, and batch writing with mocks."""

from unittest.mock import MagicMock, patch
import pytest

from src.integrations.google_sheets.client import (
    GoogleSheetsClient,
    classify_google_error,
    redact_credentials,
)


def test_redact_credentials():
    secret_text = '{"private_key": "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC5", "client_id": "12345", "access_token": "secret_token_abc"}'
    redacted = redact_credentials(secret_text)
    assert "12345" not in redacted
    assert "secret_token_abc" not in redacted
    assert "[REDACTED]" in redacted


def test_classify_google_error_api_disabled():
    api_err = Exception("APIError: [403]: Google Sheets API has not been used in project 12345 before or it is disabled.")
    perm_err = PermissionError()
    perm_err.__cause__ = api_err

    diag = classify_google_error(perm_err)
    assert "Google Sheets API disabled" in diag
    assert "https://console.developers.google.com/apis/api/sheets.googleapis.com/overview" in diag


def test_classify_google_error_file_not_found():
    fnf_err = FileNotFoundError("Credentials file not found at path: missing.json")
    diag = classify_google_error(fnf_err)
    assert "Credentials file not found" in diag
    assert "missing.json" in diag


def test_classify_google_error_service_account_permission():
    perm_err = PermissionError("403 Forbidden: The caller does not have permission")
    diag = classify_google_error(perm_err)
    assert "Service account lacks permission" in diag


def test_client_missing_credentials():
    client = GoogleSheetsClient(service_account_json="", service_account_file="")
    with patch("os.getenv", return_value=""):
        with pytest.raises(ValueError, match="Google Sheets authentication failed"):
            client.get_client()


def test_client_invalid_json_credentials():
    client = GoogleSheetsClient(service_account_json="invalid json", service_account_file="")
    with pytest.raises(ValueError, match="Invalid Google Service Account JSON"):
        client.get_client()


def test_client_verify_connection_success():
    client = GoogleSheetsClient(service_account_json='{"type": "service_account"}')

    mock_gspread_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet.title = "Test Pipeline Sheet"
    mock_gspread_client.open_by_key.return_value = mock_sheet

    with patch.object(client, "get_client", return_value=mock_gspread_client):
        ok, msg = client.verify_connection("sheet_id_123")
        assert ok is True
        assert msg == "Test Pipeline Sheet"


def test_client_verify_connection_api_disabled():
    client = GoogleSheetsClient(service_account_json='{"type": "service_account"}')

    mock_gspread_client = MagicMock()
    api_err = Exception("APIError: [403]: Google Sheets API has not been used in project 186109640309 before or it is disabled.")
    perm_err = PermissionError()
    perm_err.__cause__ = api_err
    mock_gspread_client.open_by_key.side_effect = perm_err

    with patch.object(client, "get_client", return_value=mock_gspread_client):
        ok, msg = client.verify_connection("invalid_sheet_id")
        assert ok is False
        assert "Google Sheets API disabled" in msg


def test_clear_and_write_worksheet_batching_and_idempotency():
    client = GoogleSheetsClient(service_account_json='{"type": "service_account"}')

    mock_gspread_client = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()

    mock_gspread_client.open_by_key.return_value = mock_spreadsheet
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    headers = ["h1", "h2"]
    rows = [["r1", "v1"], ["r2", "v2"], ["r3", "v3"]]

    with patch.object(client, "get_client", return_value=mock_gspread_client):
        written = client.clear_and_write_worksheet(
            spreadsheet_id="sheet_123",
            title="Research Papers",
            headers=headers,
            rows=rows,
            batch_size=2,
        )

        assert written == 3
        # Verified idempotency: clear called before writing
        mock_worksheet.clear.assert_called_once()
        # Verified batch writing (headers+rows = 4 items, batch_size=2 -> 2 append_rows calls)
        assert mock_worksheet.append_rows.call_count == 2


def test_rate_limit_retry_logic():
    client = GoogleSheetsClient(service_account_json='{"type": "service_account"}')

    attempts = 0

    def flaky_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception("429 RESOURCE_EXHAUSTED: Quota exceeded")
        return "success"

    with patch("time.sleep", return_value=None):
        res = client._execute_with_retry(flaky_func, max_retries=5, initial_delay=0.01)
        assert res == "success"
        assert attempts == 3

