"""Strongly-typed Pydantic schemas for Prompt Framework input and output."""

from typing import Any

from pydantic import BaseModel, Field


class PromptInput(BaseModel):
    """Unified container for Jinja2 template bindings."""

    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value mapping to replace Jinja2 template placeholders.",
    )


class RenderedPrompt(BaseModel):
    """The final processed system instructions, prompt text, and execution settings."""

    system_instruction: str | None = Field(
        default=None,
        description="Fully rendered system instruction persona context.",
    )
    prompt_text: str = Field(description="Fully rendered primary user prompt content.")
    template_name: str = Field(
        description="Name of the prompt template used to render."
    )
    template_version: str = Field(
        description="Version string identifier of the rendered template."
    )
    prompt_hash: str = Field(
        description="Deterministic SHA-256 fingerprint hash of the rendered prompt."
    )

    # Extended properties
    provider: str | None = Field(default=None, description="Target LLM provider name.")
    model: str | None = Field(default=None, description="Target LLM model name.")
    temperature: float | None = Field(
        default=0.0, description="Sampling temperature value."
    )
    max_output_tokens: int | None = Field(
        default=2048, description="Maximum token limits for generation."
    )
    timeout_seconds: float | None = Field(
        default=None, description="Request execution timeout period in seconds."
    )
    retry_count: int | None = Field(
        default=None, description="Number of execution retries on transient failure."
    )
    expected_response: str | None = Field(
        default=None, description="Format description of the expected output."
    )
    cacheable: bool = Field(
        default=True, description="Flag indicating if the prompt is cacheable."
    )
    telemetry_enabled: bool = Field(
        default=True, description="Flag indicating if logging/metrics are enabled."
    )
    cost_tracking: bool = Field(
        default=True, description="Flag indicating if execution cost is tracked."
    )
    tags: list[str] = Field(default_factory=list, description="Categorization tags.")
    rendered_at: str = Field(
        description="ISO 8601 timestamp recording when the prompt was rendered."
    )
    estimated_tokens: int = Field(
        default=0, description="Heuristic estimate of the prompt tokens."
    )
