"""Unit tests for JSON parsing and schema-aware structured extraction."""

import pytest
from pydantic import BaseModel, Field
from unittest.mock import AsyncMock

from src.llm.parser import JSONParser
from src.llm.exceptions import StructuredOutputError
from src.llm.orchestrator import LLMOrchestrator
from src.llm.models import LLMResponse
from tests.llm.test_orchestrator import DummyMockProvider


class SampleSchema(BaseModel):
    name: str
    count: int
    is_active: bool = True


def test_extract_json_string():
    raw_fence = "Here is the result:\n```json\n{\"name\": \"AI\", \"count\": 10}\n```\nHope that helps!"
    extracted = JSONParser.extract_json_string(raw_fence)
    assert extracted == '{"name": "AI", "count": 10}'

    raw_text = 'Response: {"name": "Test", "count": 1}'
    extracted_obj = JSONParser.extract_json_string(raw_text)
    assert extracted_obj == '{"name": "Test", "count": 1}'


def test_parse_json_dict_success():
    data = JSONParser.parse_json_dict('{"name": "Alpha", "count": 5}')
    assert data["name"] == "Alpha"
    assert data["count"] == 5


def test_parse_json_dict_malformed():
    with pytest.raises(StructuredOutputError):
        JSONParser.parse_json_dict('{"name": "Alpha", count: INVALID}')


def test_extract_structured_pydantic_valid():
    obj = JSONParser.extract_structured('{"name": "Beta", "count": 42}', target_schema=SampleSchema)
    assert isinstance(obj, SampleSchema)
    assert obj.name == "Beta"
    assert obj.count == 42


def test_extract_structured_pydantic_invalid():
    # Missing required field 'count'
    with pytest.raises(StructuredOutputError):
        JSONParser.extract_structured('{"name": "Gamma"}', target_schema=SampleSchema)


@pytest.mark.asyncio
async def test_orchestrator_structured_extraction_correction_retry():
    p1 = DummyMockProvider("gemini", "gemini-1.5-flash")
    # First call returns invalid json missing 'count'
    # Second call returns valid json
    p1.generate_mock.side_effect = [
        LLMResponse(provider="gemini", model="m", text='{"name": "Delta"}'),
        LLMResponse(provider="gemini", model="m", text='{"name": "Delta", "count": 99}'),
    ]

    orchestrator = LLMOrchestrator(providers=[p1], max_retries=1)
    result = await orchestrator.extract_structured("Extract data", target_schema=SampleSchema)

    assert result.name == "Delta"
    assert result.count == 99
    assert p1.generate_mock.call_count == 2
