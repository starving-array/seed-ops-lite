"""Unit tests for the PostgreSQL DDL Import service and parser."""

from app.services.ddl_import import DDLImportService


def test_import_single_table() -> None:
    """Verify single table import with columns, primary key, and data types mapping."""
    sql = """
    CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) NOT NULL,
        email TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    res = DDLImportService.import_schema(sql)
    assert res.success is True
    assert res.statistics.tables_imported == 1
    assert res.statistics.columns_imported == 4

    schema = res.schema_state
    assert schema is not None
    table = schema.tables[0]
    assert table.id == "users"

    # Columns checking
    col_id = table.columns[0]
    assert col_id.name == "id"
    assert col_id.type == "integer"
    assert col_id.is_primary_key is True

    col_username = table.columns[1]
    assert col_username.name == "username"
    assert col_username.type == "varchar"
    assert col_username.is_nullable is False


def test_import_multiple_tables_with_foreign_keys() -> None:
    """Verify multiple tables import containing inline and table foreign key constraints."""
    sql = """
    CREATE TABLE groups (
        group_id INT PRIMARY KEY,
        group_name VARCHAR(50) NOT NULL
    );

    CREATE TABLE members (
        member_id INT PRIMARY KEY,
        user_group_id INT REFERENCES groups(group_id),
        joined_date DATE
    );
    """
    res = DDLImportService.import_schema(sql)
    assert res.success is True
    assert res.statistics.tables_imported == 2
    assert res.statistics.relationships_imported == 1

    schema = res.schema_state
    assert schema is not None
    rel = schema.relationships[0]
    assert rel.source_table_id == "members"
    assert rel.source_column_id == "user_group_id"
    assert rel.target_table_id == "groups"
    assert rel.target_column_id == "group_id"


def test_composite_primary_keys() -> None:
    """Verify table primary key constraint parses and maps columns correctly."""
    sql = """
    CREATE TABLE user_roles (
        user_id INT,
        role_id INT,
        granted_at DATE,
        PRIMARY KEY (user_id, role_id)
    );
    """
    res = DDLImportService.import_schema(sql)
    assert res.success is True
    assert res.schema_state is not None

    table = res.schema_state.tables[0]
    assert table.columns[0].is_primary_key is True
    assert table.columns[1].is_primary_key is True
    assert table.columns[2].is_primary_key is False


def test_import_validation_and_errors() -> None:
    """Verify duplicate table names and non-existent references are rejected."""
    # 1. Non-existent referenced table
    sql_bad_ref = """
    CREATE TABLE posts (
        post_id INT PRIMARY KEY,
        author_id INT REFERENCES users(id)
    );
    """
    res = DDLImportService.import_schema(sql_bad_ref)
    assert res.success is False
    assert len(res.errors) > 0
    assert "references non-existent table" in res.errors[0].explanation

    # 2. Duplicate tables check
    sql_duplicate = """
    CREATE TABLE test (id INT);
    CREATE TABLE test (name TEXT);
    """
    res_dup = DDLImportService.import_schema(sql_duplicate)
    assert res_dup.success is False
    assert "Duplicate table names" in res_dup.errors[0].explanation
