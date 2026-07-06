"""Pydantic model representing prompt template metadata validation."""

from pydantic import BaseModel, Field


class PromptMetadata(BaseModel):
    """Pydantic model representing YAML prompt metadata."""

    name: str = Field(description="Unique human-readable identifier of the prompt.")
    version: str = Field(description="Semantic version string (e.g. '1.0.0').")
    description: str | None = Field(
        default=None, description="Detailed description of the prompt's purpose."
    )
    owner: str | None = Field(
        default=None, description="Responsible team or agent owner identifier."
    )
    provider: str | None = Field(
        default=None, description="Target LLM provider (e.g. 'Google', 'OpenAI')."
    )
    model: str | None = Field(
        default=None, description="Target LLM model string (e.g. 'gemini-2.5-flash')."
    )
    temperature: float | None = Field(
        default=0.0, description="Recommended sampling temperature."
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
        default=None, description="Summary or format of the expected response."
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
    hash_algorithm: str = Field(
        default="sha256", description="Cryptographic hash algorithm name."
    )
