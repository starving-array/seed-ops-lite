"""Airlock Validation error codes and detail structures."""

from enum import Enum

from pydantic import BaseModel, Field


class ValidationErrorCode(str, Enum):
    """Enumeration of deterministic validation error codes."""

    EMPTY_SCHEMA = "VAL-1001"
    DUPLICATE_TABLE = "VAL-1002"
    DUPLICATE_COLUMN = "VAL-1003"
    DANGEROUS_SQL = "VAL-1004"
    UNSUPPORTED_STATEMENT = "VAL-1005"
    INVALID_FK = "VAL-1006"
    INVALID_PK = "VAL-1007"
    INVALID_ENUM = "VAL-1008"
    RESERVED_KEYWORD = "VAL-1009"
    MALFORMED_DDL = "VAL-1010"


class ValidationErrorDetail(BaseModel):
    """Pydantic model representing details of a schema validation error."""

    code: ValidationErrorCode = Field(description="Structured validation error code")
    message: str = Field(description="Readable description of the error")
    location: str = Field(
        description="Where in the DDL the error was found (e.g. table name or column name)"
    )
    severity: str = Field(
        default="error",
        description="Severity level of the check (e.g. 'error' or 'warning')",
    )
    suggested_fix: str = Field(description="A suggested fix to resolve the error")
