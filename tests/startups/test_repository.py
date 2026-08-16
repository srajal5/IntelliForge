"""Tests for StartupRepository MongoDB persistence and duplicate detection."""

from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from src.models.startup import Startup
from src.storage.repositories.startups import StartupRepository


def test_startup_repository_save_and_duplicate():
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection

    # Setup exists check to return False first, then True second
    mock_collection.count_documents.side_effect = [0, 1]

    repo = StartupRepository(client=mock_client)

    startup = Startup(
        source={"name": "GitHub Organizations", "url": "https://github.com/openai"},
        content={"entityName": "OpenAI", "data": {"employeeCount": 500}},
        collectedAt=datetime.now(timezone.utc),
    )

    # First save -> Inserted (True)
    inserted1 = repo.save(startup)
    assert inserted1 is True
    assert mock_collection.insert_one.call_count == 1

    # Second save -> Duplicate (False)
    inserted2 = repo.save(startup)
    assert inserted2 is False
    # insert_one should not be called again
    assert mock_collection.insert_one.call_count == 1
