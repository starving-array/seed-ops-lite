"""Execution context for AI skill executions carrying tracing and telemetry metadata."""

from typing import Any

from pydantic import BaseModel, Field


class SkillContext(BaseModel):
    """Context holding lifecycle tracking and parameter metadata for skill execution."""

    request_id: str | None = Field(
        default=None, description="UUID tracking this specific request."
    )
    correlation_id: str | None = Field(
        default=None, description="Correlation identifier for tracing."
    )
    job_id: str | None = Field(default=None, description="Active job run identifier.")
    prompt_hash: str | None = Field(
        default=None, description="SHA-256 hash of the rendered prompt."
    )
    provider: str | None = Field(default=None, description="Target LLM provider.")
    model: str | None = Field(default=None, description="Target LLM model.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary execution metadata."
    )
