"""Data models for the Hybrid Seeder."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GenerationStrategy(str, Enum):
    """Supported generation strategies."""

    DETERMINISTIC = "deterministic"
    AI = "ai"
    HYBRID = "hybrid"


class FieldDefinition(BaseModel):
    """Specification for a single field's data generation."""

    type: str = Field(
        ...,
        description="The type of field, e.g. uuid, id, date, boolean, enum, numeric_range, rule_based, name, address, biography, description, free_text, domain_content.",
    )
    rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional generation rules and constraints, e.g. min/max values, enum choices, true probability, string length, formats.",
    )
    required: bool = Field(
        default=True,
        description="Whether the generated field is mandatory and cannot be null.",
    )


class SeedRequest(BaseModel):
    """Request parameters for synthetic data generation."""

    target: str = Field(
        ...,
        description="The target entity of the seeding operation, e.g., table name.",
    )
    num_records: int = Field(
        default=1,
        description="Number of records to generate.",
    )
    fields: dict[str, FieldDefinition] = Field(
        ...,
        description="Dictionary mapping field names to their generation definitions.",
    )
    seed: int | None = Field(
        default=None,
        description="Optional seed value to ensure deterministic and reproducible generation.",
    )
    strict: bool = Field(
        default=False,
        description="If True, raises a ValidationException when any record fails validation.",
    )


class GeneratedRecord(BaseModel):
    """Container for a single generated record's data and validation results."""

    data: dict[str, Any] = Field(
        ...,
        description="Key-value mapping of generated fields.",
    )
    validation_passed: bool = Field(
        ...,
        description="Flag indicating if the record passed all validation checks.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="List of validation errors found in the record.",
    )
    strategy_used: dict[str, GenerationStrategy] = Field(
        default_factory=dict,
        description="Map of field names to the generation strategy used.",
    )


class GenerationStatistics(BaseModel):
    """Collected metrics and statistics for a seeding execution."""

    total_records: int = Field(
        default=0,
        description="Total number of records requested.",
    )
    successful_records: int = Field(
        default=0,
        description="Number of records that successfully generated and validated.",
    )
    failed_records: int = Field(
        default=0,
        description="Number of records that failed validation checks.",
    )
    deterministic_fields_count: int = Field(
        default=0,
        description="Total number of field values generated using deterministic strategies.",
    )
    ai_fields_count: int = Field(
        default=0,
        description="Total number of field values generated using AI-assisted strategies.",
    )

    # Measured LLM metrics (strictly measured from LLMGateway)
    prompt_tokens: int = Field(
        default=0,
        description="Measured prompt tokens consumed by LLM gateway calls.",
    )
    completion_tokens: int = Field(
        default=0,
        description="Measured completion tokens consumed by LLM gateway calls.",
    )
    total_tokens: int = Field(
        default=0,
        description="Measured total tokens consumed.",
    )
    estimated_cost: float = Field(
        default=0.0,
        description="Measured monetary cost of LLM gateway calls in USD.",
    )
    latency_ms: float = Field(
        default=0.0,
        description="Measured network and execution latency of LLM gateway calls in milliseconds.",
    )


class SeedResult(BaseModel):
    """The final outcome of a synthetic data seeding operation."""

    target: str = Field(
        ...,
        description="The target entity of the seeding operation.",
    )
    records: list[GeneratedRecord] = Field(
        ...,
        description="The list of generated records.",
    )
    statistics: GenerationStatistics = Field(
        ...,
        description="Seeding execution statistics.",
    )
    success: bool = Field(
        ...,
        description="Flag indicating if the seeding operation was successful overall.",
    )
