"""Health check service — verifies connectivity and configuration."""

from __future__ import annotations

from src.config.settings import Settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HealthService:
    """Checks infrastructure connectivity and API configuration."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check(self) -> dict:
        """Run all health checks. Returns dict with 'healthy' bool and 'checks' list."""
        checks: list[dict] = []

        # MongoDB
        checks.append(self._check_mongodb())

        # LLM providers
        checks.append(self._check_configured("OpenRouter", self.settings.openrouter_api_key))
        checks.append(self._check_configured("Gemini", self.settings.gemini_api_key))
        checks.append(self._check_configured("Groq", self.settings.groq_api_key))
        checks.append(self._check_configured("DeepSeek", self.settings.deepseek_api_key))

        # External services
        checks.append(self._check_configured("GitHub API", self.settings.github_token))
        checks.append(self._check_google_sheets())

        healthy = all(c["ok"] for c in checks if c.get("required", False))
        return {"healthy": healthy, "checks": checks}

    # ------------------------------------------------------------------

    def _check_mongodb(self) -> dict:
        try:
            from pymongo import MongoClient
            client = MongoClient(
                self.settings.mongodb_uri, serverSelectionTimeoutMS=3000
            )
            client.admin.command("ping")
            client.close()
            logger.info("health_mongodb_ok")
            return {"name": "MongoDB", "ok": True, "connected": True, "required": True}
        except Exception as exc:
            logger.warning("health_mongodb_fail", error=str(exc))
            return {"name": "MongoDB", "ok": False, "connected": False, "required": True}

    @staticmethod
    def _check_configured(name: str, value: str) -> dict:
        is_placeholder = value in (
            "your_openrouter_api_key_here",
            "your_gemini_api_key_here",
            "your_groq_api_key_here",
            "your_deepseek_api_key_here",
            "your_github_token_here",
        )
        ok = bool(value and value.strip() and not is_placeholder)
        status = "Configured" if ok else "Not configured"
        return {"name": name, "ok": ok, "status": status, "required": False}

    def _check_google_sheets(self) -> dict:
        ok = bool(self.settings.google_sheets_spreadsheet_id)
        return {"name": "Google Sheets", "ok": ok, "required": False}
