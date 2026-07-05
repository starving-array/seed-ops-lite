"""PostgreSQL DDL Import Parser and Service."""

import re
import time
from typing import Any

from pydantic import BaseModel, Field

from app.platform.configuration.settings import platform_settings
from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)


class ImportErrorEntry(BaseModel):
    """Pydantic model representing an import parsing or syntax error."""

    line_number: int = Field(..., alias="lineNumber")
    statement_number: int = Field(..., alias="statementNumber")
    column_reference: str | None = Field(default=None, alias="columnReference")
    explanation: str
    suggested_correction: str | None = Field(default=None, alias="suggestedCorrection")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class ImportStatistics(BaseModel):
    """Pydantic model representing stats of the DDL import execution."""

    imports_attempted: int = Field(default=0, alias="importsAttempted")
    imports_succeeded: int = Field(default=0, alias="importsSucceeded")
    imports_failed: int = Field(default=0, alias="importsFailed")
    tables_imported: int = Field(default=0, alias="tablesImported")
    columns_imported: int = Field(default=0, alias="columnsImported")
    relationships_imported: int = Field(default=0, alias="relationshipsImported")
    average_parse_time_ms: float = Field(default=0.0, alias="averageParseTimeMs")
    validation_failures: int = Field(default=0, alias="validationFailures")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class ImportResult(BaseModel):
    """Pydantic model representing the overall result of DDL import."""

    success: bool
    schema_state: SchemaModel | None = Field(default=None, alias="schemaState")
    errors: list[ImportErrorEntry] = Field(default_factory=list)
    statistics: ImportStatistics

    class Config:
        populate_by_name = True
        populate_by_alias = True


# Type Mapper
TYPE_MAP: dict[str, str] = {
    "integer": "integer",
    "int": "integer",
    "int4": "integer",
    "bigint": "bigint",
    "int8": "bigint",
    "smallint": "smallint",
    "int2": "smallint",
    "numeric": "decimal",
    "decimal": "decimal",
    "real": "real",
    "float4": "real",
    "double precision": "double precision",
    "float8": "double precision",
    "boolean": "boolean",
    "bool": "boolean",
    "text": "text",
    "varchar": "varchar",
    "character varying": "varchar",
    "char": "char",
    "character": "char",
    "date": "date",
    "timestamp": "timestamp",
    "timestamptz": "timestamptz",
    "time": "time",
    "json": "json",
    "jsonb": "jsonb",
    "uuid": "uuid",
    "bytea": "bytea",
    "serial": "integer",
    "serial4": "integer",
    "bigserial": "bigint",
    "serial8": "bigint",
}

RESERVED_KEYWORDS = {
    "select",
    "insert",
    "update",
    "delete",
    "create",
    "drop",
    "table",
    "constraint",
    "primary",
    "foreign",
    "key",
    "references",
    "alter",
    "index",
    "from",
    "where",
    "join",
}


class DDLTokenizer:
    """Helper tokenizer to clean comments and split DDL scripts into lexical tokens."""

    @staticmethod
    def clean_comments(sql: str) -> str:
        """Remove single-line and multi-line comments."""
        # Multi-line comments
        no_multiline = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        # Single-line comments
        return re.sub(r"--.*?\n", "\n", no_multiline)

    @staticmethod
    def tokenize(sql: str) -> list[str]:
        """Convert SQL script to tokens list preserving string literals and quotes."""
        sql = DDLTokenizer.clean_comments(sql)
        tok_pattern = r"(?:'[^']*'|\"[^\"]*\"|[\w\.]+|[(),;=\[\]])"
        tokens = re.findall(tok_pattern, sql)
        # Strip quotes
        cleaned = []
        for t in tokens:
            if (
                t.startswith("'")
                and t.endswith("'")
                or t.startswith('"')
                and t.endswith('"')
            ):
                cleaned.append(t[1:-1])
            else:
                cleaned.append(t)
        return cleaned


class DDLParser:
    """Parses list of tokens into structural representation of tables and constraints."""

    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> str | None:
        """Look at token ahead without consuming."""
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def consume(self) -> str:
        """Consume and return next token."""
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def match(self, value: str) -> bool:
        """Check if next token matches value, and consume if true."""
        nxt = self.peek()
        if nxt and nxt.lower() == value.lower():
            self.consume()
            return True
        return False

    def parse(self) -> list[dict[str, Any]]:
        """Main parsing loop finding CREATE TABLE statements."""
        tables: list[dict[str, Any]] = []
        statement_index = 0

        while self.pos < len(self.tokens):
            if self.match("create"):
                if self.match("table"):
                    # We have a CREATE TABLE!
                    table_name = self.consume()
                    # Skip 'if not exists' if present
                    if (
                        table_name.lower() == "if"
                        and self.match("not")
                        and self.match("exists")
                    ):
                        table_name = self.consume()

                    if not self.match("("):
                        continue

                    # Parse contents inside parentheses
                    columns: list[dict[str, Any]] = []
                    constraints: list[dict[str, Any]] = []

                    # Balance parentheses to parse columns block
                    depth = 1
                    block_tokens: list[str] = []
                    while self.pos < len(self.tokens) and depth > 0:
                        t = self.consume()
                        if t == "(":
                            depth += 1
                        elif t == ")":
                            depth -= 1
                            if depth == 0:
                                break
                        block_tokens.append(t)

                    # Parse block tokens split by comma
                    self._parse_table_body(block_tokens, columns, constraints)

                    tables.append(
                        {
                            "name": table_name,
                            "columns": columns,
                            "constraints": constraints,
                            "statement_index": statement_index,
                        }
                    )
                    statement_index += 1
            else:
                self.consume()

        return tables

    def _parse_table_body(
        self,
        tokens: list[str],
        columns: list[dict[str, Any]],
        constraints: list[dict[str, Any]],
    ) -> None:
        # Split tokens by top-level commas (ignoring commas inside inner parentheses)
        parts: list[list[str]] = []
        current: list[str] = []
        depth = 0
        for t in tokens:
            if t == "(":
                depth += 1
                current.append(t)
            elif t == ")":
                depth -= 1
                current.append(t)
            elif t == "," and depth == 0:
                parts.append(current)
                current = []
            else:
                current.append(t)
        if current:
            parts.append(current)

        for p in parts:
            if not p:
                continue
            first = p[0].lower()
            # Table constraints
            if first in ("primary", "foreign", "unique", "constraint"):
                self._parse_table_constraint(p, constraints)
            else:
                # Column definition
                self._parse_column_def(p, columns)

    def _parse_column_def(
        self, tokens: list[str], columns: list[dict[str, Any]]
    ) -> None:
        if len(tokens) < 2:
            return
        col_name = tokens[0]
        # Resolve type
        # Handle composite type names like "double precision" or "character varying"
        type_tokens = []
        i = 1
        while i < len(tokens):
            val = tokens[i].lower()
            if val in (
                "(",
                ",",
                "primary",
                "foreign",
                "unique",
                "not",
                "null",
                "default",
                "check",
                "references",
            ):
                break
            type_tokens.append(tokens[i])
            i += 1

        col_type = " ".join(type_tokens)

        # Check if type has parameters (e.g. varchar(255))
        if i < len(tokens) and tokens[i] == "(":
            # Skip parameters
            depth = 1
            i += 1
            while i < len(tokens) and depth > 0:
                if tokens[i] == "(":
                    depth += 1
                elif tokens[i] == ")":
                    depth -= 1
                i += 1

        # Check inline constraints
        is_pk = False
        is_nullable = True
        default_val = ""
        fk_ref = None

        while i < len(tokens):
            tok = tokens[i].lower()
            if (
                tok == "primary"
                and i + 1 < len(tokens)
                and tokens[i + 1].lower() == "key"
            ):
                is_pk = True
                i += 2
            elif (
                tok == "not" and i + 1 < len(tokens) and tokens[i + 1].lower() == "null"
            ):
                is_nullable = False
                i += 2
            elif tok == "null":
                is_nullable = True
                i += 1
            elif tok == "unique":
                i += 1
            elif tok == "default" and i + 1 < len(tokens):
                default_val = tokens[i + 1]
                i += 2
            elif tok == "references" and i + 1 < len(tokens):
                ref_table = tokens[i + 1]
                ref_col = None
                if i + 2 < len(tokens) and tokens[i + 2] == "(":
                    ref_col = tokens[i + 3]
                fk_ref = {"table": ref_table, "column": ref_col}
                break  # Simplification: references is the last clause parsed
            else:
                i += 1

        columns.append(
            {
                "name": col_name,
                "type": col_type,
                "is_primary_key": is_pk,
                "is_nullable": is_nullable,
                "default_value": default_val,
                "fk_ref": fk_ref,
            }
        )

    def _parse_table_constraint(
        self, tokens: list[str], constraints: list[dict[str, Any]]
    ) -> None:
        idx = 0
        name = None
        if tokens[idx].lower() == "constraint":
            name = tokens[idx + 1]
            idx += 2

        ctype = tokens[idx].lower()
        if ctype == "primary" and tokens[idx + 1].lower() == "key":
            # Primary key columns
            cols = []
            if tokens[idx + 2] == "(":
                j = idx + 3
                while j < len(tokens) and tokens[j] != ")":
                    if tokens[j] != ",":
                        cols.append(tokens[j])
                    j += 1
            constraints.append(
                {
                    "type": "primary_key",
                    "name": name,
                    "columns": cols,
                }
            )
        elif ctype == "foreign" and tokens[idx + 1].lower() == "key":
            # Foreign Key Table Constraint
            # syntax: FOREIGN KEY (col) REFERENCES ref_table(ref_col)
            source_cols = []
            j = idx + 2
            if tokens[j] == "(":
                j += 1
                while j < len(tokens) and tokens[j] != ")":
                    if tokens[j] != ",":
                        source_cols.append(tokens[j])
                    j += 1
                j += 1

            if j < len(tokens) and tokens[j].lower() == "references":
                ref_table = tokens[j + 1]
                target_cols = []
                if j + 2 < len(tokens) and tokens[j + 2] == "(":
                    k = j + 3
                    while k < len(tokens) and tokens[k] != ")":
                        if tokens[k] != ",":
                            target_cols.append(tokens[k])
                        k += 1
                constraints.append(
                    {
                        "type": "foreign_key",
                        "name": name,
                        "source_columns": source_cols,
                        "target_table": ref_table,
                        "target_columns": target_cols,
                    }
                )


class DDLImportService:
    """Orchestrates tokenization, parsing, validation, type mapping, and relationship resolution."""

    @staticmethod
    def import_schema(sql: str) -> ImportResult:
        """Validate and generate the SafeSeedOps SchemaModel from a raw SQL DDL script."""
        start_time = time.perf_counter()
        stats = ImportStatistics(importsAttempted=1)
        errors: list[ImportErrorEntry] = []

        # 1. Size Validation
        if len(sql.encode("utf-8")) > platform_settings.PLATFORM_DDL_MAX_SQL_SIZE:
            errors.append(
                ImportErrorEntry(
                    lineNumber=1,
                    statementNumber=0,
                    explanation="SQL script exceeds maximum size limit.",
                    suggestedCorrection="Reduce DDL size.",
                )
            )
            stats.imports_failed = 1
            return ImportResult(success=False, errors=errors, statistics=stats)

        # 2. Tokenize and Parse
        tokens = DDLTokenizer.tokenize(sql)
        parser = DDLParser(tokens)
        try:
            parsed_tables = parser.parse()
        except Exception as e:
            errors.append(
                ImportErrorEntry(
                    lineNumber=1,
                    statementNumber=0,
                    explanation=f"Syntax parsing failure: {e!s}",
                )
            )
            stats.imports_failed = 1
            return ImportResult(success=False, errors=errors, statistics=stats)

        # 3. Limit Validations
        if len(parsed_tables) > platform_settings.PLATFORM_DDL_MAX_TABLE_COUNT:
            errors.append(
                ImportErrorEntry(
                    lineNumber=1,
                    statementNumber=0,
                    explanation="Table count exceeds configuration limit.",
                )
            )
            stats.imports_failed = 1
            return ImportResult(success=False, errors=errors, statistics=stats)

        # Map to SchemaModel structures
        tables_list: list[TableModel] = []
        relationships_list: list[RelationshipModel] = []

        # Track counts
        tot_cols = 0
        for pt in parsed_tables:
            tot_cols += len(pt["columns"])
        if tot_cols > platform_settings.PLATFORM_DDL_MAX_COLUMN_COUNT:
            errors.append(
                ImportErrorEntry(
                    lineNumber=1,
                    statementNumber=0,
                    explanation="Column count exceeds configuration limit.",
                )
            )
            stats.imports_failed = 1
            return ImportResult(success=False, errors=errors, statistics=stats)

        # Validate duplicate table names
        table_names = [t["name"].lower() for t in parsed_tables]
        if len(table_names) != len(set(table_names)):
            errors.append(
                ImportErrorEntry(
                    lineNumber=1,
                    statementNumber=0,
                    explanation="Duplicate table names detected.",
                )
            )
            stats.validation_failures += 1

        # Populate tables and columns
        for pt in parsed_tables:
            cols: list[ColumnModel] = []
            # Check duplicate columns
            col_names = [c["name"].lower() for c in pt["columns"]]
            if len(col_names) != len(set(col_names)):
                errors.append(
                    ImportErrorEntry(
                        lineNumber=1,
                        statementNumber=pt["statement_index"],
                        explanation=f"Duplicate column names detected in table '{pt['name']}'.",
                    )
                )
                stats.validation_failures += 1

            for pc in pt["columns"]:
                # Type Mapping
                mapped_type = TYPE_MAP.get(pc["type"].lower(), "varchar")

                # Check reserved keywords
                if pc["name"].lower() in RESERVED_KEYWORDS:
                    errors.append(
                        ImportErrorEntry(
                            lineNumber=1,
                            statementNumber=pt["statement_index"],
                            columnReference=pc["name"],
                            explanation="Column name is a reserved SQL keyword.",
                            suggestedCorrection=f"Rename '{pc['name']}' to avoid query syntax issues.",
                        )
                    )
                    stats.validation_failures += 1

                cols.append(
                    ColumnModel(
                        id=pc["name"],
                        name=pc["name"],
                        type=mapped_type,
                        isPrimaryKey=pc["is_primary_key"],
                        isNullable=pc["is_nullable"],
                        defaultValue=pc["default_value"],
                    )
                )

            # Map Table Constraint PKs if present
            for constraint in pt["constraints"]:
                if constraint["type"] == "primary_key":
                    for pk_col in constraint["columns"]:
                        for c in cols:
                            if c.name.lower() == pk_col.lower():
                                # Workaround to set pk true (Pydantic model is frozen by Config, but ColumnModel is not frozen)
                                object.__setattr__(c, "is_primary_key", True)

            tables_list.append(
                TableModel(
                    id=pt["name"],
                    name=pt["name"],
                    columns=cols,
                )
            )

        # Relationship detection and mapping
        rel_index = 0
        for pt in parsed_tables:
            # Inline Column FKs
            for pc in pt["columns"]:
                if pc["fk_ref"]:
                    ref_table = pc["fk_ref"]["table"]
                    ref_col = (
                        pc["fk_ref"]["column"] or pc["name"]
                    )  # Fallback to current name if col omitted

                    # Validate referenced table exists
                    if ref_table.lower() not in table_names:
                        errors.append(
                            ImportErrorEntry(
                                lineNumber=1,
                                statementNumber=pt["statement_index"],
                                explanation=f"Table '{pt['name']}' references non-existent table '{ref_table}'.",
                            )
                        )
                        stats.validation_failures += 1
                        continue

                    relationships_list.append(
                        RelationshipModel(
                            id=f"rel_{rel_index}",
                            name=f"fk_{pt['name']}_{pc['name']}",
                            sourceTableId=pt["name"],
                            sourceColumnId=pc["name"],
                            targetTableId=ref_table,
                            targetColumnId=ref_col,
                            type="ManyToOne",
                            isRequired=not pc["is_nullable"],
                            cascadeDelete=False,
                            cascadeUpdate=False,
                        )
                    )
                    rel_index += 1

            # Table Constraint FKs
            for constraint in pt["constraints"]:
                if constraint["type"] == "foreign_key":
                    ref_table = constraint["target_table"]
                    # If multiple columns are present, map them individually
                    for s_col, t_col in zip(
                        constraint["source_columns"],
                        constraint["target_columns"],
                        strict=False,
                    ):
                        if ref_table.lower() not in table_names:
                            errors.append(
                                ImportErrorEntry(
                                    lineNumber=1,
                                    statementNumber=pt["statement_index"],
                                    explanation=f"Table constraint references non-existent table '{ref_table}'.",
                                )
                            )
                            stats.validation_failures += 1
                            continue

                        relationships_list.append(
                            RelationshipModel(
                                id=f"rel_{rel_index}",
                                name=f"fk_{pt['name']}_{s_col}",
                                sourceTableId=pt["name"],
                                sourceColumnId=s_col,
                                targetTableId=ref_table,
                                targetColumnId=t_col,
                                type="ManyToOne",
                                isRequired=True,
                                cascadeDelete=False,
                                cascadeUpdate=False,
                            )
                        )
                        rel_index += 1

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Populate Stats
        stats.tables_imported = len(tables_list)
        stats.columns_imported = tot_cols
        stats.relationships_imported = len(relationships_list)
        stats.average_parse_time_ms = duration_ms

        success = len(errors) == 0
        if success:
            stats.imports_succeeded = 1
            schema_state = SchemaModel(
                tables=tables_list, relationships=relationships_list
            )
        else:
            stats.imports_failed = 1
            schema_state = None

        return ImportResult(
            success=success,
            schemaState=schema_state,
            errors=errors,
            statistics=stats,
        )
