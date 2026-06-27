"""Unit and integration tests for the Airlock Validation layer."""

import pytest

from app.validation.ddl_validator import DDLValidator
from app.validation.regex_validator import RegexValidator
from app.validation.security_validator import SecurityValidator
from app.validation.validation_errors import ValidationErrorCode
from app.validation.validator import AirlockValidator


@pytest.fixture
def validator() -> AirlockValidator:
    """Fixture returning an instance of AirlockValidator."""
    return AirlockValidator(
        regex_validator=RegexValidator(),
        ddl_validator=DDLValidator(),
        security_validator=SecurityValidator(),
    )


@pytest.mark.asyncio
async def test_valid_schema(validator: AirlockValidator) -> None:
    """Test validation of a completely clean and valid DDL schema."""
    ddl = """
    CREATE TABLE groups (
        id INT PRIMARY KEY,
        group_name VARCHAR(100) NOT NULL
    );

    CREATE TABLE users (
        id INT PRIMARY KEY,
        username VARCHAR(50) NOT NULL,
        group_id INT,
        FOREIGN KEY (group_id) REFERENCES groups (id)
    );
    """
    result = await validator.validate_schema(ddl)
    assert result.success is True
    assert len(result.errors) == 0
    assert result.execution_allowed is True


@pytest.mark.asyncio
async def test_drop_table(validator: AirlockValidator) -> None:
    """Test that DDL containing dangerous DROP statements is rejected."""
    ddl = "DROP TABLE users;"
    result = await validator.validate_schema(ddl)
    assert result.success is False
    assert result.execution_allowed is False
    assert any(err.code == ValidationErrorCode.DANGEROUS_SQL for err in result.errors)


@pytest.mark.asyncio
async def test_duplicate_tables(validator: AirlockValidator) -> None:
    """Test that defining the same table name twice is rejected."""
    ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(50)
    );

    CREATE TABLE users (
        id INT PRIMARY KEY,
        email VARCHAR(100)
    );
    """
    result = await validator.validate_schema(ddl)
    assert result.success is False
    assert any(err.code == ValidationErrorCode.DUPLICATE_TABLE for err in result.errors)


@pytest.mark.asyncio
async def test_duplicate_columns(validator: AirlockValidator) -> None:
    """Test that defining the same column twice in a table is rejected."""
    ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        username VARCHAR(50),
        username VARCHAR(100)
    );
    """
    result = await validator.validate_schema(ddl)
    assert result.success is False
    assert any(
        err.code == ValidationErrorCode.DUPLICATE_COLUMN for err in result.errors
    )


@pytest.mark.asyncio
async def test_missing_pk(validator: AirlockValidator) -> None:
    """Test that tables without primary keys are rejected."""
    ddl = """
    CREATE TABLE log_events (
        event_id INT,
        log_message TEXT
    );
    """
    result = await validator.validate_schema(ddl)
    assert result.success is False
    assert any(err.code == ValidationErrorCode.INVALID_PK for err in result.errors)


@pytest.mark.asyncio
async def test_invalid_fk(validator: AirlockValidator) -> None:
    """Test that invalid foreign keys referencing missing columns/tables fail."""
    # Scenario A: Referenced Table is missing
    ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        role_id INT,
        FOREIGN KEY (role_id) REFERENCES roles (id)
    );
    """
    result = await validator.validate_schema(ddl)
    assert result.success is False
    assert any(err.code == ValidationErrorCode.INVALID_FK for err in result.errors)

    # Scenario B: Referenced Column in referenced table is missing
    ddl2 = """
    CREATE TABLE roles (
        id INT PRIMARY KEY,
        role_name VARCHAR(50)
    );

    CREATE TABLE users (
        id INT PRIMARY KEY,
        role_id INT,
        FOREIGN KEY (role_id) REFERENCES roles (uuid)
    );
    """
    result2 = await validator.validate_schema(ddl2)
    assert result2.success is False
    assert any(err.code == ValidationErrorCode.INVALID_FK for err in result2.errors)


@pytest.mark.asyncio
async def test_malformed_sql(validator: AirlockValidator) -> None:
    """Test that syntax errors like unmatched parentheses or quotes fail."""
    # Unmatched parenthesis
    ddl1 = "CREATE TABLE users (id INT PRIMARY KEY;"
    result1 = await validator.validate_schema(ddl1)
    assert result1.success is False
    assert any(err.code == ValidationErrorCode.MALFORMED_DDL for err in result1.errors)

    # Unmatched quotes
    ddl2 = "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(50) CHECK (name IN ('admin', 'user)));"
    result2 = await validator.validate_schema(ddl2)
    assert result2.success is False
    assert any(err.code == ValidationErrorCode.MALFORMED_DDL for err in result2.errors)


@pytest.mark.asyncio
async def test_empty_input(validator: AirlockValidator) -> None:
    """Test that empty or whitespace-only inputs are rejected."""
    result = await validator.validate_schema("   ")
    assert result.success is False
    assert any(err.code == ValidationErrorCode.EMPTY_SCHEMA for err in result.errors)


@pytest.mark.asyncio
async def test_unsupported_statements(validator: AirlockValidator) -> None:
    """Test that commands other than CREATE TABLE/TYPE (e.g. INSERT) are blocked."""
    ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(50)
    );

    INSERT INTO users (id, name) VALUES (1, 'Alice');
    """
    result = await validator.validate_schema(ddl)
    assert result.success is False
    assert any(
        err.code == ValidationErrorCode.UNSUPPORTED_STATEMENT for err in result.errors
    )


@pytest.mark.asyncio
async def test_validation_metadata(validator: AirlockValidator) -> None:
    """Test that ValidationResult metadata, hashes, stats, and suggestions are correctly generated."""
    # Scenario A: Valid DDL schema
    ddl = """
    CREATE TABLE groups (
        id INT PRIMARY KEY,
        group_name VARCHAR(100)
    );

    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(50),
        group_id INT REFERENCES groups (id)
    );
    """
    result = await validator.validate_schema(ddl)
    assert result.success is True
    assert result.validator_version == "1.0.0"
    assert len(result.schema_hash) == 64  # valid SHA-256 length
    assert result.statistics.rule_count == 13
    assert result.statistics.table_count == 2
    assert result.statistics.column_count == 5
    assert result.statistics.error_count == 0
    assert len(result.suggestions) == 1
    assert result.suggestions[0].rule_id == "RULE-GEN-01"
    assert result.suggestions[0].confidence == 1.00

    # Scenario B: Invalid DDL schema with missing PK and reserved keyword as column
    ddl_invalid = """
    CREATE TABLE users (
        id INT,
        where VARCHAR(50)
    );
    """
    result_invalid = await validator.validate_schema(ddl_invalid)
    assert result_invalid.success is False
    assert result_invalid.statistics.error_count == 2
    # Ensure suggestions contain structured metadata with confidence scores
    suggestions = {s.rule_id: s for s in result_invalid.suggestions}
    assert "RULE-SEM-03" in suggestions  # Missing PK
    assert suggestions["RULE-SEM-03"].confidence == 1.00
    assert "RULE-SEM-04" in suggestions  # Reserved Keyword as Column name
    assert suggestions["RULE-SEM-04"].confidence == 0.97
