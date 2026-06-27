"""Strongly typed models for the Binding Engine."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Supported relationship cardinality types."""

    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"


class RelationshipReference(BaseModel):
    """Defines a relationship bind constraint between parent and child columns."""

    local_column: str = Field(
        ..., description="The foreign key column name in the child table."
    )
    referenced_table: str = Field(
        ..., description="The parent table name being referenced."
    )
    referenced_column: str = Field(
        ..., description="The primary key column name in the parent table."
    )
    relationship_type: RelationshipType = Field(
        default=RelationshipType.MANY_TO_ONE,
        description="The cardinality of the relationship.",
    )


class BindingRequest(BaseModel):
    """Input payload for a binding execution run."""

    records: dict[str, list[dict[str, Any]]] = Field(
        ...,
        description="Dictionary mapping table names to lists of generated record dicts.",
    )
    schema_ddl: str = Field(
        ...,
        description="The database SQL DDL schema defining tables and foreign keys.",
    )
    relationships: dict[str, list[RelationshipReference]] = Field(
        default_factory=dict,
        description="Optional manual overrides for table relationships.",
    )


class BoundRecord(BaseModel):
    """Represents a single record after foreign key binding."""

    table_name: str = Field(..., description="The table this record belongs to.")
    data: dict[str, Any] = Field(
        ..., description="The record data dictionary containing resolved foreign keys."
    )


class BindingStatistics(BaseModel):
    """Statistics consolidated during the binding operation."""

    total_records: int = Field(
        default=0, description="Total number of records received."
    )
    bound_records: int = Field(
        default=0, description="Number of records that were modified or had keys bound."
    )
    unresolved_references_count: int = Field(
        default=0, description="Count of foreign key fields that could not be resolved."
    )
    integrity_violations_count: int = Field(
        default=0, description="Count of referential integrity check violations."
    )
    duration_ms: float = Field(
        default=0.0, description="Execution duration in milliseconds."
    )


class BindingResult(BaseModel):
    """Outcome of resolving and validating relationships on generated records."""

    records: dict[str, list[BoundRecord]] = Field(
        ..., description="Map of table names to bound record models."
    )
    statistics: BindingStatistics = Field(
        ..., description="Binding performance and tracking statistics."
    )
    success: bool = Field(
        ...,
        description="Boolean indicating if binding resolved and validated without critical errors.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="List of validation errors or dependency failures encountered.",
    )
