"""Unit and integration tests for the LLM Gateway and Gemini provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.settings.config import settings
from app.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.llm.gateway import LLMGateway
from app.llm.models import LLMRequest
from app.llm.provider import GeminiProvider


@pytest.mark.asyncio
async def test_gemini_provider_success() -> None:
    """Test successful Gemini API completion call."""
    request = LLMRequest(
        prompt="CREATE TABLE test (id INT);",
        temperature=0.1,
        max_tokens=100,
        system_instruction="Analyze schema",
    )

    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(settings, "GEMINI_API_KEY", "mock-key"),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Schema analyzed successfully. No errors."}]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 15,
                "candidatesTokenCount": 25,
                "totalTokenCount": 40,
            },
        }
        mock_post.return_value = mock_response

        provider = GeminiProvider()
        response = await provider.generate(request)

        assert response.text == "Schema analyzed successfully. No errors."
        assert response.usage.model == settings.GEMINI_MODEL
        assert response.usage.provider == "Google"
        assert response.usage.prompt_tokens == 15
        assert response.usage.completion_tokens == 25
        assert response.usage.total_tokens == 40
        assert response.usage.estimated_cost > 0.0


@pytest.mark.asyncio
async def test_gemini_provider_token_fallback() -> None:
    """Test token count fallback estimation when metadata is missing."""
    request = LLMRequest(prompt="CREATE TABLE fallback (id INT);")

    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(settings, "GEMINI_API_KEY", "mock-key"),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Estimation text response"}]},
                    "finishReason": "STOP",
                }
            ]
            # No usageMetadata provided
        }
        mock_post.return_value = mock_response

        provider = GeminiProvider()
        response = await provider.generate(request)

        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0
        assert (
            response.usage.total_tokens
            == response.usage.prompt_tokens + response.usage.completion_tokens
        )


@pytest.mark.asyncio
async def test_gemini_provider_missing_key() -> None:
    """Test configuration exception raised when API key is missing."""
    request = LLMRequest(prompt="Test prompt")
    with (
        patch.object(settings, "GEMINI_API_KEY", None),
        patch.object(settings, "GOOGLE_API_KEY", None),
    ):
        provider = GeminiProvider()
        with pytest.raises(LLMConfigurationError):
            await provider.generate(request)


@pytest.mark.asyncio
async def test_gemini_provider_rate_limit() -> None:
    """Test rate limit exception raised on HTTP 429."""
    request = LLMRequest(prompt="Test prompt")
    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(settings, "GEMINI_API_KEY", "mock-key"),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = "Quota exceeded"
        mock_post.return_value = mock_response

        provider = GeminiProvider()
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.generate(request)
        assert exc_info.value.recoverable is True


@pytest.mark.asyncio
async def test_gemini_provider_transient_server_error() -> None:
    """Test standard transient server failure on HTTP 503."""
    request = LLMRequest(prompt="Test prompt")
    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(settings, "GEMINI_API_KEY", "mock-key"),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_post.return_value = mock_response

        provider = GeminiProvider()
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate(request)
        assert exc_info.value.recoverable is True


@pytest.mark.asyncio
async def test_gemini_provider_non_recoverable_client_error() -> None:
    """Test non-recoverable exception raised on HTTP 400."""
    request = LLMRequest(prompt="Test prompt")
    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(settings, "GEMINI_API_KEY", "mock-key"),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request parameter options"
        mock_post.return_value = mock_response

        provider = GeminiProvider()
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate(request)
        assert exc_info.value.recoverable is False


@pytest.mark.asyncio
async def test_gemini_provider_timeout() -> None:
    """Test request timeout handling."""
    request = LLMRequest(prompt="Test prompt")
    with (
        patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")),
        patch.object(settings, "GEMINI_API_KEY", "mock-key"),
    ):
        provider = GeminiProvider()
        with pytest.raises(LLMTimeoutError):
            await provider.generate(request)


@pytest.mark.asyncio
async def test_gateway_json_mode_validation() -> None:
    """Test that JSON mode output validation correctly succeeds or fails."""
    # Case A: Valid JSON response
    request_valid = LLMRequest(prompt="Generate JSON", json_mode=True)
    gateway = LLMGateway()

    with patch.object(gateway, "_provider", new_callable=AsyncMock) as mock_provider:
        response = MagicMock()
        response.text = '{"status": "success", "data": 123}'
        response.usage.prompt_tokens = 5
        response.usage.completion_tokens = 5
        response.usage.estimated_cost = 0.001
        response.usage.model = "mock-model"
        mock_provider.generate.return_value = response

        result = await gateway.generate(request_valid)
        assert result.text == '{"status": "success", "data": 123}'

    # Case B: Invalid JSON response
    request_invalid = LLMRequest(prompt="Generate JSON", json_mode=True)
    with patch.object(gateway, "_provider", new_callable=AsyncMock) as mock_provider:
        response = MagicMock()
        response.text = "This is not valid JSON content"
        response.usage.prompt_tokens = 5
        response.usage.completion_tokens = 5
        response.usage.estimated_cost = 0.001
        response.usage.model = "mock-model"
        mock_provider.generate.return_value = response

        with pytest.raises(LLMValidationError):
            await gateway.generate(request_invalid)


@pytest.mark.asyncio
async def test_gateway_retry_mechanism() -> None:
    """Test that gateway retries transient/recoverable errors and stops on non-recoverable."""
    gateway = LLMGateway()

    # Case A: Recoverable Rate Limit Error succeeds on second attempt
    request = LLMRequest(prompt="Retrying prompt")
    mock_provider = AsyncMock()

    # Define side effect: first call rate limit, second call success
    response_success = MagicMock()
    response_success.text = "Success response"
    response_success.usage.prompt_tokens = 5
    response_success.usage.completion_tokens = 5
    response_success.usage.estimated_cost = 0.001
    response_success.usage.model = "mock-model"

    mock_provider.generate.side_effect = [
        LLMRateLimitError("Rate limit exceeded"),
        response_success,
    ]

    with (
        patch.object(gateway, "_provider", mock_provider),
        patch.object(settings, "LLM_MAX_RETRIES", 2),
    ):
        result = await gateway.generate(request)
        assert result.text == "Success response"
        assert mock_provider.generate.call_count == 2

    # Case B: Non-recoverable error fails instantly without retrying
    mock_provider_fail = AsyncMock()
    mock_provider_fail.generate.side_effect = LLMProviderError(
        "Invalid API options", recoverable=False
    )

    with (
        patch.object(gateway, "_provider", mock_provider_fail),
        patch.object(settings, "LLM_MAX_RETRIES", 2),
    ):
        with pytest.raises(LLMProviderError):
            await gateway.generate(request)
        assert mock_provider_fail.generate.call_count == 1


@pytest.mark.asyncio
async def test_gateway_accepts_rendered_prompt() -> None:
    """Test that the gateway accepts a RenderedPrompt, extracts details and calls provider."""
    from app.prompts.models import RenderedPrompt

    rendered = RenderedPrompt(
        system_instruction="You are a SQL validator.",
        prompt_text="SELECT 1;",
        template_name="schema_validation",
        template_version="1.0.0",
        prompt_hash="dummy-hash-1234567890abcdef",
        provider="Google",
        model="gemini-2.5-flash",
        temperature=0.2,
        max_output_tokens=1000,
        timeout_seconds=45.0,
        retry_count=5,
        expected_response="JSON response structure",
        rendered_at="2026-06-26T23:45:00Z",
        estimated_tokens=5,
    )

    gateway = LLMGateway()
    mock_provider = AsyncMock()

    mock_response = MagicMock()
    mock_response.text = '{"valid": true}'
    mock_response.usage.prompt_tokens = 5
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 15
    mock_response.usage.estimated_cost = 0.0001
    mock_response.usage.model = "gemini-2.5-flash"
    mock_response.usage.provider = "Google"

    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        result = await gateway.generate(rendered)

        assert result.text == '{"valid": true}'

        # Verify provider.generate was called with converted LLMRequest
        called_args, called_kwargs = mock_provider.generate.call_args
        request_arg = called_args[0]

        assert request_arg.prompt == "SELECT 1;"
        assert request_arg.system_instruction == "You are a SQL validator."
        assert request_arg.model == "gemini-2.5-flash"
        assert request_arg.temperature == 0.2
        assert request_arg.max_tokens == 1000
        # expected_response contains JSON, so json_mode should be True
        assert request_arg.json_mode is True

        # Verify timeout was passed to provider.generate
        assert called_kwargs["timeout"] == 45.0
