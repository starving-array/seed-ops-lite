"""Strongly-typed Pydantic request and response models for the LLM Gateway."""

from typing import Any

from pydantic import BaseModel, Field

from app.telemetry.token_usage import TokenUsage


class LLMRequest(BaseModel):
    """Model representing a unified request parameters to language models."""

    prompt: str = Field(description="The main text prompt for the LLM.")
    model: str | None = Field(
        default=None,
        description="Optional model identifier override (defaults to configured model).",
    )
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature between 0.0 and 2.0 (defaults to 0.0).",
    )
    max_tokens: int = Field(
        default=2048,
        description="Maximum tokens to generate in the completion response.",
    )
    system_instruction: str | None = Field(
        default=None,
        description="Optional system instruction or persona constraints.",
    )
    json_mode: bool = Field(
        default=False,
        description="If True, forces the response format to be structured JSON.",
    )


class LLMResponse(BaseModel):
    """Model representing a unified response from the LLM Gateway."""

    text: str = Field(description="The generated raw response text content.")
    usage: TokenUsage = Field(
        description="Standardized token accounting and latency metrics."
    )
    raw_response: dict[str, Any] = Field(
        default_factory=dict,
        description="The raw payload structure returned by the provider.",
    )
    request_id: str | None = Field(
        default=None, description="UUID tracking this particular request."
    )
    correlation_id: str | None = Field(
        default=None, description="Correlation identifier for tracing."
    )
