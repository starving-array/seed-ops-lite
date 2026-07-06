"""Unit tests for the AI Contract Layer covering parsing, validation, and error classification."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, Field

from app.llm.contracts.exceptions import (
    AIContractParsingError,
    AIContractValidationError,
)
from app.llm.contracts.normalizer import AIContractNormalizer
from app.llm.contracts.parser import extract_json_payload, parse_to_dict
from app.llm.contracts.request import AIContractRequest
from app.llm.contracts.validator import validate_schema
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMResponse
from app.prompts.models import RenderedPrompt
from app.telemetry.token_usage import TokenUsage


# Simple schema for testing
class UserTestSchema(BaseModel):
    username: str
    age: int
    is_active: bool = True
    skills: list[str] = Field(default_factory=list)


def test_extract_json_payload() -> None:
    """Test extracting JSON content out of standard strings and markdown fences."""
    # Case A: Plain JSON string
    plain = '{"a": 1}'
    assert extract_json_payload(plain) == plain

    # Case B: Markdown code fences with json marker
    markdown_json = '```json\n{\n  "a": 1\n}\n```'
    assert extract_json_payload(markdown_json) == '{\n  "a": 1\n}'

    # Case C: Markdown code fences without json marker
    markdown_plain = '```\n{\n  "a": 1\n}\n```'
    assert extract_json_payload(markdown_plain) == '{\n  "a": 1\n}'


def test_parse_to_dict_success() -> None:
    """Test parsing standard JSON strings to dictionaries."""
    raw = '{"username": "alice", "age": 30}'
    result = parse_to_dict(raw)
    assert result["username"] == "alice"
    assert result["age"] == 30


def test_parse_to_dict_failures() -> None:
    """Test that parsing invalid, empty, or non-object structures fails."""
    # Case A: Empty string
    with pytest.raises(AIContractParsingError) as exc:
        parse_to_dict("   ")
    assert "content is empty" in str(exc.value)

    # Case B: Malformed JSON
    with pytest.raises(AIContractParsingError) as exc:
        parse_to_dict('{"username": "alice"')
    assert "Malformed JSON payload" in str(exc.value)

    # Case C: JSON list instead of object
    with pytest.raises(AIContractParsingError) as exc:
        parse_to_dict("[1, 2, 3]")
    assert "Expected JSON object" in str(exc.value)


def test_validate_schema_success() -> None:
    """Test validating parsed dictionary against schema succeeds when correct."""
    data = {"username": "bob", "age": 25, "skills": ["python"]}
    obj = validate_schema(data, UserTestSchema)
    assert obj.username == "bob"
    assert obj.age == 25
    assert obj.is_active is True
    assert obj.skills == ["python"]


def test_validate_schema_failures() -> None:
    """Test schema validation fails when required fields are missing or types mismatch."""
    # Case A: Missing required field 'username'
    data_missing = {"age": 25}
    with pytest.raises(AIContractValidationError) as exc:
        validate_schema(data_missing, UserTestSchema)
    assert "Field required" in str(exc.value.errors)

    # Case B: Type mismatch on 'age' (e.g. string that cannot be coerced to int)
    data_bad_type = {"username": "bob", "age": "not-a-number"}
    with pytest.raises(AIContractValidationError) as exc:
        validate_schema(data_bad_type, UserTestSchema)
    assert "Input should be a valid integer" in str(exc.value.errors)


@pytest.mark.asyncio
async def test_execute_contract_success() -> None:
    """Test standard successful contract execution."""
    rendered = RenderedPrompt(
        system_instruction="sys",
        prompt_text="user",
        template_name="test_tmpl",
        template_version="1.1.0",
        prompt_hash="hash-value",
        rendered_at="2026-06-26T23:59:00Z",
    )
    request = AIContractRequest[UserTestSchema](
        prompt=rendered, response_schema=UserTestSchema
    )

    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(
        provider="Google",
        model="gemini-2.5-flash",
        latency_ms=450.0,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost=0.0002,
    )
    mock_response = LLMResponse(
        text='{"username": "alice", "age": 28}',
        usage=usage,
        raw_response={"candidates": [{"finishReason": "STOP"}]},
        request_id="req-id",
        correlation_id="corr-id",
    )

    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        result = await AIContractNormalizer.execute_contract(gateway, request)

        assert result.success is True
        assert result.data is not None
        assert result.data.username == "alice"
        assert result.data.age == 28
        assert result.metadata.request_id is not None
        assert result.metadata.correlation_id == "corr-id"

        assert result.metadata.provider == "Google"
        assert result.metadata.model == "gemini-2.5-flash"
        assert result.metadata.prompt_hash == "hash-value"
        assert result.metadata.prompt_version == "1.1.0"
        assert result.metadata.finish_reason == "STOP"
        assert result.metadata.total_tokens == 150


@pytest.mark.asyncio
async def test_execute_contract_provider_failure() -> None:
    """Test contract execution failure during gateway provider call."""
    rendered = RenderedPrompt(
        system_instruction="sys",
        prompt_text="user",
        template_name="test_tmpl",
        template_version="1.1.0",
        prompt_hash="hash-value",
        rendered_at="2026-06-26T23:59:00Z",
    )
    request = AIContractRequest[UserTestSchema](
        prompt=rendered, response_schema=UserTestSchema
    )

    gateway = LLMGateway()
    mock_provider = AsyncMock()
    mock_provider.generate.side_effect = LLMProviderError(
        "API connection timeout", recoverable=True
    )

    with patch.object(gateway, "_provider", mock_provider):
        result = await AIContractNormalizer.execute_contract(gateway, request)

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert result.error.error_type == "provider"
        assert result.error.is_retryable is True
        assert "API connection timeout" in result.error.message


@pytest.mark.asyncio
async def test_execute_contract_parsing_failure() -> None:
    """Test contract execution failure when response is malformed JSON."""
    rendered = RenderedPrompt(
        system_instruction="sys",
        prompt_text="user",
        template_name="test_tmpl",
        template_version="1.1.0",
        prompt_hash="hash-value",
        rendered_at="2026-06-26T23:59:00Z",
    )
    request = AIContractRequest[UserTestSchema](
        prompt=rendered, response_schema=UserTestSchema
    )

    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(
        provider="Google",
        model="gemini-2.5-flash",
        latency_ms=300.0,
        prompt_tokens=100,
        completion_tokens=0,
        total_tokens=100,
        estimated_cost=0.0,
    )
    # Invalid JSON syntax that cannot be repaired
    mock_response = LLMResponse(
        text="This is not JSON at all!",
        usage=usage,
        raw_response={},
        request_id="req-id",
        correlation_id="corr-id",
    )

    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        result = await AIContractNormalizer.execute_contract(gateway, request)

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert result.error.error_type == "parsing"
        assert result.error.is_retryable is False
        assert (
            "JSON validation" in result.error.message
            or "Malformed JSON" in result.error.message
        )


@pytest.mark.asyncio
async def test_execute_contract_validation_failure() -> None:
    """Test contract execution failure when schema constraints are violated."""
    rendered = RenderedPrompt(
        system_instruction="sys",
        prompt_text="user",
        template_name="test_tmpl",
        template_version="1.1.0",
        prompt_hash="hash-value",
        rendered_at="2026-06-26T23:59:00Z",
    )
    request = AIContractRequest[UserTestSchema](
        prompt=rendered, response_schema=UserTestSchema
    )

    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(
        provider="Google",
        model="gemini-2.5-flash",
        latency_ms=300.0,
        prompt_tokens=100,
        completion_tokens=10,
        total_tokens=110,
        estimated_cost=0.0001,
    )
    # 'age' should be int, but we pass string that fails coercion
    mock_response = LLMResponse(
        text='{"username": "alice", "age": "not-valid"}',
        usage=usage,
        raw_response={},
        request_id="req-id",
        correlation_id="corr-id",
    )

    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        result = await AIContractNormalizer.execute_contract(gateway, request)

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert result.error.error_type == "validation"
        assert result.error.is_retryable is False
        assert "Validation failed for schema UserTestSchema" in result.error.message
        assert len(result.error.raw_details["errors"]) > 0
