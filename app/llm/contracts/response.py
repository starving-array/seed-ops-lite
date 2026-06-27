"""Strongly-typed Pydantic response models for the contract layer."""

from typing import Any, Generic

from pydantic import BaseModel, Field

from app.llm.contracts.base import T


class ContractMetadata(BaseModel):
    """Telemetry and tracking metadata for LLM contract execution."""

    request_id: str | None = Field(
        default=None, description="UUID tracking this request."
    )
    correlation_id: str | None = Field(
        default=None, description="Correlation identifier for tracing."
    )
    provider: str = Field(..., description="API provider name.")
    model: str = Field(..., description="Target model name.")
    prompt_hash: str | None = Field(
        default=None, description="SHA-256 hash of the rendered prompt."
    )
    prompt_version: str | None = Field(
        default=None, description="Prompt template version."
    )
    latency_ms: float = Field(
        default=0.0, description="Network and execution latency in milliseconds."
    )
    prompt_tokens: int = Field(default=0, description="Tokens in the prompt request.")
    completion_tokens: int = Field(
        default=0, description="Tokens in the generated response."
    )
    total_tokens: int = Field(default=0, description="Total tokens consumed.")
    estimated_cost: float = Field(default=0.0, description="Estimated cost in USD.")
    finish_reason: str | None = Field(
        default=None, description="Completion finish reason."
    )


class ContractErrorDetails(BaseModel):
    """Standardized representation of execution, validation, or parsing failure."""

    message: str = Field(..., description="Error message description.")
    error_type: str = Field(
        ...,
        description="Classification category: provider, validation, parsing, system, etc.",
    )
    is_retryable: bool = Field(
        ..., description="Flag indicating if the failure is transient/retryable."
    )
    raw_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Underlying exception or validation error details.",
    )


class AIContractResponse(BaseModel, Generic[T]):
    """Unified normalized result returned to client business logic."""

    success: bool = Field(..., description="Boolean indicating contract success.")
    data: T | None = Field(
        default=None, description="The validated, parsed schema data model."
    )
    error: ContractErrorDetails | None = Field(
        default=None, description="Details of the error if success is False."
    )
    metadata: ContractMetadata = Field(
        ..., description="Telemetry and execution tracking metadata."
    )
