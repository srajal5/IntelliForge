"""Google Sheets API Client.

Handles Google service-account authentication, rate-limiting, error handling,
credential redaction, worksheet creation/clearing, and batch updates.
"""

from __future__ import annotations

import json
import os
import re
import time
import random
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def redact_credentials(text: str) -> str:
    """Sanitize strings by redacting private keys, tokens, and sensitive fields."""
    if not text:
        return ""
    # Redact private key patterns (multiline or escaped)
    text = re.sub(
        r"-----BEGIN PRIVATE KEY-----[\s\S]*?-----END PRIVATE KEY-----",
        "[REDACTED_PRIVATE_KEY]",
        text,
    )
    text = re.sub(r'"private_key":\s*"[^"]+"', '"private_key": "[REDACTED]"', text)
    text = re.sub(r'"client_id":\s*"[^"]+"', '"client_id": "[REDACTED]"', text)
    text = re.sub(r'"client_secret":\s*"[^"]+"', '"client_secret": "[REDACTED]"', text)
    text = re.sub(r'"private_key_id":\s*"[^"]+"', '"private_key_id": "[REDACTED]"', text)
    text = re.sub(r'"refresh_token":\s*"[^"]+"', '"refresh_token": "[REDACTED]"', text)
    text = re.sub(r'"access_token":\s*"[^"]+"', '"access_token": "[REDACTED]"', text)

    # Redact authorization headers & tokens
    text = re.sub(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)authorization:\s*[^\s,]+", "Authorization: [REDACTED]", text)
    text = re.sub(r"key=[a-zA-Z0-9_\-]+", "key=[REDACTED]", text)
    return text


def classify_google_error(exc: Exception) -> str:
    """Classify Google API/auth exceptions into clear, actionable, redacted diagnostic messages."""
    raw_str = str(exc).strip()
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    cause_str = str(cause).strip() if cause else ""

    combined = f"{raw_str} {cause_str} {repr(exc)} {repr(cause) if cause else ''}"
    detail_msg = redact_credentials(raw_str or cause_str or repr(exc))

    # 1. API Disabled
    if "sheets.googleapis.com" in combined or ("Google Sheets API" in combined and ("disabled" in combined or "has not been used" in combined)):
        return (
            "Google Sheets API disabled: The Google Sheets API is not enabled for this GCP project. "
            f"Enable it at: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview (Details: {detail_msg})"
        )
    if "drive.googleapis.com" in combined or ("Google Drive API" in combined and ("disabled" in combined or "has not been used" in combined)):
        return (
            "Google Drive API disabled: The Google Drive API is not enabled for this GCP project. "
            f"Enable it at: https://console.developers.google.com/apis/api/drive.googleapis.com/overview (Details: {detail_msg})"
        )

    # 2. Credentials file not found
    if isinstance(exc, FileNotFoundError) or "No such file or directory" in combined or "file not found" in combined.lower():
        return f"Credentials file not found: {detail_msg}"

    # 3. Invalid service account JSON
    if isinstance(exc, json.JSONDecodeError) or "Invalid Google Service Account JSON" in combined or "JSONDecodeError" in combined:
        return f"Invalid service-account JSON: {detail_msg}"

    # 4. Authentication failure
    if any(k in combined for k in ["invalid_grant", "invalid_claim", "Signature verification failed", "GoogleAuthError", "DefaultCredentialsError", "401"]):
        return f"Authentication failure: {detail_msg}"

    # 5. Spreadsheet not accessible / not found
    if "SpreadsheetNotFound" in combined or "404" in combined or "NOT_FOUND" in combined:
        return f"Spreadsheet not accessible (not found or invalid ID): {detail_msg}"

    # 6. Service account lacks permission
    if isinstance(exc, PermissionError) or "403" in combined or "PermissionDenied" in combined or "permission" in combined.lower():
        return (
            "Service account lacks permission: Ensure spreadsheet is shared with service account email. "
            f"Details: {detail_msg}"
        )

    # 7. Worksheet creation/access failure
    if "WorksheetNotFound" in combined or "worksheet" in combined.lower():
        return f"Worksheet creation/access failure: {detail_msg}"

    # 8. Network / TLS failure
    if any(net in combined for net in ["Connection refused", "Failed to establish a new connection", "Name or service not known", "SSL", "gaierror", "URLError", "TimeoutError", "socket"]):
        return f"Network/TLS failure: {detail_msg}"

    # Default fallback
    return f"Google API Error [{type(exc).__name__}]: {detail_msg}"


class GoogleSheetsClient:
    """Client wrapper for Google Sheets API operations using gspread and google-auth."""

    def __init__(
        self,
        service_account_json: str = "",
        service_account_file: str = "",
    ) -> None:
        self.service_account_json = service_account_json
        self.service_account_file = service_account_file
        self._gspread_client = None

    def _get_credentials(self):
        """Build Google credentials from JSON string or file path safely."""
        from google.oauth2.service_account import Credentials

        if self.service_account_json and self.service_account_json.strip():
            try:
                info = json.loads(self.service_account_json)
                return Credentials.from_service_account_info(info, scopes=SCOPES)
            except Exception as exc:
                diagnostic = classify_google_error(exc)
                logger.error("google_sheets_auth_json_failed", error=diagnostic)
                raise ValueError(f"Invalid Google Service Account JSON: {diagnostic}") from None

        filepath = (
            self.service_account_file
            or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
            or os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")
        )
        if filepath:
            if not os.path.exists(filepath):
                msg = f"Credentials file not found at path: {filepath}"
                logger.error("google_sheets_credentials_file_not_found", path=filepath)
                raise FileNotFoundError(msg)
            try:
                return Credentials.from_service_account_file(filepath, scopes=SCOPES)
            except Exception as exc:
                diagnostic = classify_google_error(exc)
                logger.error("google_sheets_auth_file_failed", error=diagnostic)
                raise ValueError(f"Failed loading credentials from {filepath}: {diagnostic}") from None

        raise ValueError(
            "Google Sheets authentication failed: neither valid GOOGLE_SERVICE_ACCOUNT_JSON "
            "nor existing GOOGLE_SERVICE_ACCOUNT_FILE was provided."
        )

    def get_client(self):
        """Get or initialize gspread Client singleton instance."""
        if self._gspread_client is None:
            import gspread

            creds = self._get_credentials()
            self._gspread_client = gspread.authorize(creds)
        return self._gspread_client

    def _execute_with_retry(self, func, max_retries: int = 5, initial_delay: float = 1.0):
        """Execute a function with exponential backoff and jitter for rate limit (429) retries."""
        delay = initial_delay
        for attempt in range(1, max_retries + 1):
            try:
                return func()
            except Exception as exc:
                err_msg = str(exc)
                sanitized_msg = redact_credentials(err_msg)

                # Check if rate limit (429 / quota exceeded)
                is_rate_limit = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg

                if is_rate_limit and attempt < max_retries:
                    jitter = random.uniform(0, 0.5)
                    sleep_time = delay + jitter
                    logger.warning(
                        "google_sheets_rate_limit_retry",
                        attempt=attempt,
                        next_retry_in=round(sleep_time, 2),
                    )
                    time.sleep(sleep_time)
                    delay *= 2.0
                else:
                    diagnostic = classify_google_error(exc)
                    logger.error("google_sheets_api_error", attempt=attempt, error=diagnostic)
                    raise RuntimeError(f"Google Sheets API call failed: {diagnostic}") from None

    def verify_connection(self, spreadsheet_id: str) -> tuple[bool, str]:
        """Verify authentication and spreadsheet access. Returns (success, spreadsheet_title_or_error)."""
        if not spreadsheet_id:
            return (False, "Spreadsheet ID is missing.")

        try:
            client = self.get_client()
            spreadsheet = client.open_by_key(spreadsheet_id)
            return (True, spreadsheet.title)
        except Exception as exc:
            diagnostic = classify_google_error(exc)
            return (False, diagnostic)

    def clear_and_write_worksheet(
        self,
        spreadsheet_id: str,
        title: str,
        headers: list[str],
        rows: list[list[Any]],
        batch_size: int = 500,
    ) -> int:
        """Clear worksheet (or create if missing) and batch write header + rows.

        Returns total rows written (excluding header).
        """
        client = self.get_client()

        def _op():
            spreadsheet = client.open_by_key(spreadsheet_id)

            # Get or create worksheet
            try:
                worksheet = spreadsheet.worksheet(title)
            except Exception:
                worksheet = spreadsheet.add_worksheet(
                    title=title,
                    rows=max(len(rows) + 10, 100),
                    cols=max(len(headers), 10),
                )

            # Idempotency: Clear worksheet contents
            worksheet.clear()

            all_data = [headers] + rows

            # Batch write
            batch_size_actual = max(1, batch_size)
            for i in range(0, len(all_data), batch_size_actual):
                chunk = all_data[i : i + batch_size_actual]
                worksheet.append_rows(chunk, value_input_option="USER_ENTERED")

            # Apply structured formatting
            self._apply_worksheet_formatting(worksheet, headers=headers, total_rows=len(all_data))

            return len(rows)

        return self._execute_with_retry(_op)

    def _apply_worksheet_formatting(self, worksheet, headers: list[str], total_rows: int) -> None:
        """Apply freeze row, header styling, basic filter, text wrapping, and auto-column sizing."""
        try:
            # 1. Freeze header row
            worksheet.freeze(rows=1)

            num_cols = len(headers)
            if num_cols > 0:
                def _col_letter(col_idx: int) -> str:
                    result = ""
                    while col_idx > 0:
                        col_idx, remainder = divmod(col_idx - 1, 26)
                        result = chr(65 + remainder) + result
                    return result

                last_col_letter = _col_letter(num_cols)
                header_range = f"A1:{last_col_letter}1"

                # 2. Bold & styled header format
                worksheet.format(
                    header_range,
                    {
                        "textFormat": {
                            "bold": True,
                            "fontSize": 10,
                            "foregroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
                        },
                        "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 0.98},
                        "horizontalAlignment": "LEFT",
                    },
                )

                # 3. Apply basic filter across headers/data
                try:
                    worksheet.set_basic_filter()
                except Exception:
                    pass

                # 4. Text wrap data cells
                if total_rows > 1:
                    full_range = f"A2:{last_col_letter}{total_rows}"
                    try:
                        worksheet.format(
                            full_range,
                            {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"},
                        )
                    except Exception:
                        pass

                # 5. Auto resize columns
                try:
                    worksheet.columns_auto_resize(0, num_cols)
                except Exception:
                    pass

        except Exception as exc:
            logger.warning("google_sheets_formatting_warning", error=str(exc))


