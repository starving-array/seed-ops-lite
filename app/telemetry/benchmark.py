"""System benchmark and performance report models."""

from pydantic import BaseModel, Field

from app.telemetry.token_usage import TokenUsage


class BenchmarkReport(BaseModel):
    """Pydantic model representing system benchmark reports."""

    execution_time_seconds: float = Field(description="Total execution time in seconds")
    rows_generated: int = Field(description="Number of database rows generated")
    rows_per_second: float = Field(description="Generation speed in rows/second")
    token_usage: TokenUsage = Field(description="Aggregated token usage details")
    estimated_cost: float = Field(description="Aggregated monetary cost in USD")
    retry_count: int = Field(
        default=0, description="Number of execution retries performed"
    )
    cache_hits: int = Field(default=0, description="Number of cache hits")
    cache_misses: int = Field(default=0, description="Number of cache misses")
    worker_count: int = Field(
        default=1, description="Number of concurrent workers active"
    )
    integrity_score: float = Field(
        default=1.0,
        description="Database integrity score (0.0 to 1.0)",
    )
