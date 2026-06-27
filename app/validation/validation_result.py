"""Validation result schema representation for the Airlock Validation layer."""

from pydantic import BaseModel, Field

from app.validation.validation_errors import ValidationErrorDetail


class ValidationSuggestion(BaseModel):
    """Pydantic model representing suggestion metadata for DDL remediation."""

    rule_id: str = Field(description="The unique identifier of the validation rule")
    message: str = Field(description="Friendly message explaining the suggestion")
    suggested_fix: str = Field(description="Recommended fix or code correction")
    confidence: float = Field(
        description="Confidence score of the suggestion (typically 0.95 to 1.00)"
    )


class ValidationStatistics(BaseModel):
    """Pydantic model representing validation run statistics."""

    rule_count: int = Field(description="Total number of rules executed")
    table_count: int = Field(description="Total number of tables parsed")
    column_count: int = Field(description="Total number of columns parsed")
    error_count: int = Field(description="Total number of errors found")
    warning_count: int = Field(description="Total number of warnings found")


class ValidationResult(BaseModel):
    """Structured validation results from the Airlock Validation layer."""

    success: bool = Field(description="True if validation passed without errors")
    validator_version: str = Field(description="Version of the validator engine")
    validation_timestamp: str = Field(
        description="ISO 8601 timestamp of validation run"
    )
    validation_duration_ms: float = Field(
        description="Total duration of validation in milliseconds"
    )
    schema_hash: str = Field(description="Deterministic SHA-256 hash of the schema")
    errors: list[ValidationErrorDetail] = Field(
        default_factory=list, description="List of blocking errors found"
    )
    warnings: list[str] = Field(
        default_factory=list, description="List of non-blocking warnings"
    )
    suggestions: list[ValidationSuggestion] = Field(
        default_factory=list, description="List of structured suggestion metadata"
    )
    statistics: ValidationStatistics = Field(
        description="Statistical breakdown of the validation run"
    )
    validated_schema: str = Field(
        description="The cleaned and validated SQL DDL schema text"
    )
    execution_allowed: bool = Field(
        description="True if the schema is safe to proceed to LLM generation"
    )
