"""Token usage Pydantic models for tracking LLM operations and costs."""

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Pydantic model representing token accounting metrics for LLM executions."""

    model: str = Field(
        description="The model name used (e.g. gpt-4o, gemini-2.5-flash)"
    )
    provider: str = Field(
        description="The API provider name (e.g. OpenAI, Google, Anthropic)"
    )
    prompt_tokens: int | None = Field(
        default=None, description="Number of tokens in the prompt"
    )
    completion_tokens: int | None = Field(
        default=None, description="Number of tokens in the completion response"
    )
    total_tokens: int | None = Field(
        default=None, description="Total tokens consumed (prompt + completion)"
    )
    estimated_cost: float | None = Field(
        default=None, description="Estimated monetary cost of the API call in USD"
    )
    latency_ms: float = Field(
        default=0.0,
        description="Network and execution latency of the API call in milliseconds",
    )
