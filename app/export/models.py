"""Strongly typed models for the Export Engine."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExportFormat(str, Enum):
    """Supported serialization export formats."""

    JSON = "json"
    CSV = "csv"


class ExportStatistics(BaseModel):
    """Execution statistics consolidated during the export operation."""

    total_records: int = Field(
        default=0, description="Total number of records processed."
    )
    total_tables: int = Field(
        default=0, description="Total number of tables processed."
    )
    file_size_bytes: int = Field(
        default=0, description="Total size in bytes of the serialized data."
    )
    duration_ms: float = Field(
        default=0.0, description="Execution duration in milliseconds."
    )


class ExportRequest(BaseModel):
    """Input payload for an export execution run."""

    records: dict[str, list[dict[str, Any]]] = Field(
        ...,
        description="Dictionary mapping table names to lists of generated record dicts.",
    )
    format: str = Field(
        ...,
        description="The target serialization export format (e.g. 'json', 'csv' or custom registered format).",
    )
    target_directory: str | None = Field(
        default=None,
        description="Optional output file path directory to persist files on disk.",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional format-specific options (e.g. delimiter, indent).",
    )


class ExportResult(BaseModel):
    """Outcome of serializing the dataset."""

    success: bool = Field(
        ...,
        description="Boolean indicating if export completed without critical errors.",
    )
    serialized_data: dict[str, bytes] = Field(
        default_factory=dict,
        description="Map of output identifiers (e.g. filename/key) to serialized bytes.",
    )
    output_files: dict[str, str] = Field(
        default_factory=dict,
        description="Map of table names or dataset identifier to actual files written on disk.",
    )
    statistics: ExportStatistics = Field(
        ...,
        description="Export performance and tracking statistics.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="List of validation errors or write failures encountered.",
    )
