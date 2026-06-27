"""Strongly-typed Pydantic models for the schema validation skills."""

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """Structure representing a single validation or styling finding."""

    severity: str = Field(..., description="Severity level: low, medium, or high.")
    description: str = Field(
        ..., description="Description of the pattern or issue found."
    )
    suggestion: str | None = Field(
        default=None, description="Suggested action to address this finding."
    )


class SchemaValidationInput(BaseModel):
    """Common input data parameters carrying target SQL schema for validation skills."""

    schema_ddl: str = Field(..., description="Raw SQL DDL command commands to analyze.")


class StructureValidationResult(BaseModel):
    """Validated structural analysis outcome containing PKs, completeness, and completeness issues."""

    is_valid: bool = Field(
        ..., description="True if layout design is structurally complete."
    )
    table_count: int = Field(..., description="Number of tables identified.")
    observations: list[str] = Field(
        default_factory=list, description="General structural observations."
    )
    findings: list[Finding] = Field(
        default_factory=list, description="Structural issues identified."
    )


class RelationshipsValidationResult(BaseModel):
    """Validated foreign keys, Loops, cardinality check findings."""

    is_valid: bool = Field(
        ..., description="True if relationship rules are valid and safe."
    )
    fk_count: int = Field(..., description="Number of foreign keys identified.")
    observations: list[str] = Field(
        default_factory=list, description="Relational integrity observations."
    )
    findings: list[Finding] = Field(
        default_factory=list,
        description="Foreign key loop, orphan, or layout findings.",
    )


class NamingValidationResult(BaseModel):
    """Validated casing, standards, naming layout observations."""

    is_valid: bool = Field(..., description="True if schema names follow conventions.")
    observations: list[str] = Field(
        default_factory=list, description="Style and casing observations."
    )
    findings: list[Finding] = Field(
        default_factory=list, description="Violations of naming standards."
    )


class DataQualityValidationResult(BaseModel):
    """Validated nullability, default values constraints findings."""

    is_valid: bool = Field(
        ..., description="True if constraint types support data loading."
    )
    observations: list[str] = Field(
        default_factory=list, description="Nullability and defaults observations."
    )
    findings: list[Finding] = Field(
        default_factory=list, description="Data seeding or check issues."
    )


class BestPracticesValidationResult(BaseModel):
    """Validated performance index suggestions and scalability designs."""

    is_valid: bool = Field(
        ..., description="True if layout follows scalability design rules."
    )
    observations: list[str] = Field(
        default_factory=list, description="Indexing and performance observations."
    )
    findings: list[Finding] = Field(
        default_factory=list, description="Performance tuning design suggestions."
    )
