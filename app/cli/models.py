"""Strongly typed data models for the CLI Application."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExitStatus(int, Enum):
    """CLI execution exit code statuses mapping."""

    SUCCESS = 0
    VALIDATION_ERROR = 1
    PLANNING_ERROR = 2
    GENERATION_ERROR = 3
    EXPORT_ERROR = 4
    CONFIGURATION_ERROR = 5
    RUNTIME_ERROR = 6
    UNKNOWN_ERROR = 99


class CLIRequest(BaseModel):
    """Represents a validated CLI request parameters payload."""

    command: str = Field(..., description="The CLI command name to run.")
    ddl_path: str | None = Field(
        default=None, description="Path to the DDL schema file."
    )
    ddl_content: str | None = Field(
        default=None, description="Direct SQL DDL schema text."
    )
    num_records: int = Field(
        default=10, description="Default number of records to generate per table."
    )
    row_targets: dict[str, int] = Field(
        default_factory=dict, description="Row count targets per table."
    )
    seed: int | None = Field(
        default=None, description="Optional seed for deterministic generation."
    )
    export_format: str = Field(
        default="json", description="Target export format (json, csv)."
    )
    output_dir: str | None = Field(
        default=None, description="Output directory to serialize tables."
    )
    profile: str | None = Field(
        default=None, description="Optional config profile overrides."
    )
    config_file: str | None = Field(
        default=None, description="Optional runtime config file."
    )


class ExecutionSummary(BaseModel):
    """Consolidated performance metrics and execution results summary."""

    total_tables: int = Field(default=0, description="Total tables processed.")
    total_records: int = Field(default=0, description="Total records generated.")
    duration_ms: float = Field(
        default=0.0, description="Execution duration in milliseconds."
    )
    success: bool = Field(
        default=True, description="Whether execution succeeded overall."
    )
    statistics: dict[str, Any] = Field(
        default_factory=dict, description="Consolidated metrics/statistics dictionary."
    )


class CLIResult(BaseModel):
    """Unified command execution result wrapped container."""

    exit_code: ExitStatus = Field(
        ..., description="The command execution exit status code."
    )
    message: str = Field(..., description="User-facing status summary description.")
    data: Any = Field(
        default=None, description="Command execution returned data payload."
    )
    summary: ExecutionSummary | None = Field(
        default=None, description="Consolidated execution statistics."
    )


class CommandContext(BaseModel):
    """Execution context tracing details for command-line runs."""

    request: CLIRequest = Field(..., description="The parsed CLI request model.")
    correlation_id: str = Field(..., description="Correlation ID tracing key.")
