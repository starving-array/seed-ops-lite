"""DDL semantic validator validating tables, columns, PK/FK integrity, and syntax."""

import re

from app.validation.validation_errors import ValidationErrorCode, ValidationErrorDetail

RESERVED_KEYWORDS = {
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "FROM",
    "WHERE",
    "TABLE",
    "CREATE",
    "DROP",
    "INDEX",
    "VIEW",
    "DATABASE",
    "USER",
    "PASSWORD",
    "PRIMARY",
    "FOREIGN",
    "REFERENCES",
    "JOIN",
    "ON",
    "GROUP",
    "BY",
    "ORDER",
    "HAVING",
    "LIMIT",
    "KEY",
}


class ColumnDef:
    """Represents a parsed SQL column definition."""

    def __init__(
        self,
        name: str,
        data_type: str,
        is_pk: bool = False,
        is_nullable: bool = True,
        fk_ref: tuple[str, str] | None = None,
    ) -> None:
        """Initialize ColumnDef."""
        self.name = name
        self.data_type = data_type
        self.is_pk = is_pk
        self.is_nullable = is_nullable
        self.fk_ref = fk_ref


class TableDef:
    """Represents a parsed SQL table definition."""

    def __init__(self, name: str) -> None:
        """Initialize TableDef."""
        self.name = name
        self.columns: dict[str, ColumnDef] = {}
        self.pk_columns: set[str] = set()
        self.fk_constraints: list[tuple[str, str, str]] = (
            []
        )  # (local_col, ref_table, ref_col)


class DDLValidator:
    """DDL semantic validator validating tables, columns, PK/FK integrity, and syntax."""

    def __init__(self) -> None:
        """Initialize DDLValidator."""
        self.last_parsed_tables: dict[str, TableDef] = {}

    def validate(self, ddl: str) -> list[ValidationErrorDetail]:
        """Validate DDL structure, column semantics, PK/FK links, and keywords.

        Args:
            ddl: Cleaned DDL string.

        Returns:
            List[ValidationErrorDetail]: List of semantic errors found.
        """
        errors: list[ValidationErrorDetail] = []

        # 1. Clean comments
        cleaned = re.sub(r"--.*", "", ddl)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

        tables: dict[str, TableDef] = {}

        # Parse tables
        pos = 0
        while True:
            match = re.search(
                r"\bCREATE\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
                cleaned[pos:],
                re.IGNORECASE,
            )
            if not match:
                break

            table_name = match.group(1)
            tbl_start_idx = pos + match.start()

            # Check for duplicate table name
            if table_name.lower() in tables:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.DUPLICATE_TABLE,
                        message=f"Duplicate table name '{table_name}' defined.",
                        location=f"Table '{table_name}'",
                        severity="error",
                        suggested_fix="Rename the duplicate table or remove it.",
                    )
                )

            table_def = TableDef(table_name)

            # Find opening parenthesis of table definition
            paren_start = cleaned.find("(", tbl_start_idx + match.end() - match.start())
            if paren_start == -1:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.MALFORMED_DDL,
                        message=f"Missing opening parenthesis for table '{table_name}'.",
                        location=f"Table '{table_name}'",
                        severity="error",
                        suggested_fix="Add '(' to start the table body definition.",
                    )
                )
                pos = tbl_start_idx + match.end()
                continue

            # Find matching closing parenthesis
            paren_depth = 1
            idx = paren_start + 1
            while idx < len(cleaned) and paren_depth > 0:
                char = cleaned[idx]
                if char == "(":
                    paren_depth += 1
                elif char == ")":
                    paren_depth -= 1
                idx += 1

            if paren_depth > 0:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.MALFORMED_DDL,
                        message=f"Unclosed table definition body for table '{table_name}'.",
                        location=f"Table '{table_name}'",
                        severity="error",
                        suggested_fix="Add a matching ')' at the end of the table definition.",
                    )
                )
                pos = idx
                continue

            body = cleaned[paren_start + 1 : idx - 1].strip()

            # Split columns by comma ignoring commas inside parameter parenthesis e.g. decimal(10,2)
            lines = []
            curr_line: list[str] = []
            depth = 0
            for char in body:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1

                if char == "," and depth == 0:
                    lines.append("".join(curr_line).strip())
                    curr_line = []
                else:
                    curr_line.append(char)
            if curr_line:
                lines.append("".join(curr_line).strip())

            # Parse columns and constraints
            for line in lines:
                if not line:
                    continue

                # Table-level Primary Key: PRIMARY KEY (col1, col2)
                pk_match = re.match(r"^PRIMARY\s+KEY\s*\((.*?)\)", line, re.IGNORECASE)
                if pk_match:
                    cols = [
                        c.strip().strip('"').strip("`")
                        for c in pk_match.group(1).split(",")
                    ]
                    for col in cols:
                        table_def.pk_columns.add(col)
                    continue

                # Table-level Foreign Key: FOREIGN KEY (col) REFERENCES ref_tbl (ref_col)
                fk_match = re.match(
                    r"^FOREIGN\s+KEY\s*\((.*?)\)\s*REFERENCES\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)",
                    line,
                    re.IGNORECASE,
                )
                if fk_match:
                    local_col = fk_match.group(1).strip().strip('"').strip("`")
                    ref_table = fk_match.group(2).strip()
                    ref_col = fk_match.group(3).strip().strip('"').strip("`")
                    table_def.fk_constraints.append((local_col, ref_table, ref_col))
                    continue

                # Standard Column: <name> <type> [constraints...]
                col_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+(.*)", line)
                if not col_match:
                    continue

                col_name = col_match.group(1)
                col_rest = col_match.group(2).strip()

                # Check reserved keywords
                if col_name.upper() in RESERVED_KEYWORDS:
                    errors.append(
                        ValidationErrorDetail(
                            code=ValidationErrorCode.RESERVED_KEYWORD,
                            message=(
                                f"Reserved SQL keyword '{col_name}' used as column "
                                f"name in table '{table_name}'."
                            ),
                            location=f"Table '{table_name}', Column '{col_name}'",
                            severity="error",
                            suggested_fix=f"Rename column '{col_name}' to a non-reserved identifier.",
                        )
                    )

                # Check duplicates
                if col_name.lower() in table_def.columns:
                    errors.append(
                        ValidationErrorDetail(
                            code=ValidationErrorCode.DUPLICATE_COLUMN,
                            message=(
                                f"Duplicate column name '{col_name}' defined in table "
                                f"'{table_name}'."
                            ),
                            location=f"Table '{table_name}', Column '{col_name}'",
                            severity="error",
                            suggested_fix="Rename the duplicate column or remove it.",
                        )
                    )

                is_pk = False
                is_nullable = True
                if re.search(r"\bNOT\s+NULL\b", col_rest, re.IGNORECASE):
                    is_nullable = False
                elif re.search(r"\bNULL\b", col_rest, re.IGNORECASE):
                    is_nullable = True
                if re.search(r"\bPRIMARY\s+KEY\b", col_rest, re.IGNORECASE):
                    is_pk = True
                    is_nullable = False
                    table_def.pk_columns.add(col_name)

                fk_ref = None
                inline_fk_match = re.search(
                    r"\bREFERENCES\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)",
                    col_rest,
                    re.IGNORECASE,
                )
                if inline_fk_match:
                    ref_table = inline_fk_match.group(1).strip()
                    ref_col = inline_fk_match.group(2).strip().strip('"').strip("`")
                    fk_ref = (ref_table, ref_col)
                    table_def.fk_constraints.append((col_name, ref_table, ref_col))

                # Check invalid Enum definitions (unquoted literals in check constraints)
                if "CHECK" in col_rest.upper() and "IN" in col_rest.upper():
                    in_match = re.search(r"\bIN\s*\((.*?)\)", col_rest, re.IGNORECASE)
                    if in_match:
                        enum_values = in_match.group(1).split(",")
                        for val_raw in enum_values:
                            val = val_raw.strip()
                            if not (val.startswith("'") and val.endswith("'")) and not (
                                val.startswith('"') and val.endswith('"')
                            ):
                                errors.append(
                                    ValidationErrorDetail(
                                        code=ValidationErrorCode.INVALID_ENUM,
                                        message=(
                                            f"Invalid ENUM definition in check constraint: "
                                            f"'{val}' is not quoted."
                                        ),
                                        location=f"Table '{table_name}', Column '{col_name}'",
                                        severity="error",
                                        suggested_fix="Ensure all enum values are quoted string literals.",
                                    )
                                )

                type_match = re.match(
                    r"^([a-zA-Z_][a-zA-Z0-9_]*(?:\(.*?\))?)", col_rest, re.IGNORECASE
                )
                data_type = type_match.group(1) if type_match else "UNKNOWN"

                column_def = ColumnDef(col_name, data_type, is_pk, is_nullable, fk_ref)
                table_def.columns[col_name.lower()] = column_def

            tables[table_name.lower()] = table_def
            pos = idx

        self.last_parsed_tables = tables

        # Semantic verification
        for table_def in tables.values():
            # Check Missing PK
            if not table_def.pk_columns:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.INVALID_PK,
                        message=f"Table '{table_def.name}' is missing a Primary Key.",
                        location=f"Table '{table_def.name}'",
                        severity="error",
                        suggested_fix="Define a PRIMARY KEY column or constraint for this table.",
                    )
                )
            else:
                # Check PK columns exist
                for pk_col in table_def.pk_columns:
                    if pk_col.lower() not in table_def.columns:
                        errors.append(
                            ValidationErrorDetail(
                                code=ValidationErrorCode.INVALID_PK,
                                message=(
                                    f"Primary key column '{pk_col}' does not exist in "
                                    f"table '{table_def.name}'."
                                ),
                                location=f"Table '{table_def.name}'",
                                severity="error",
                                suggested_fix="Ensure primary key refers to a defined column.",
                            )
                        )

            # Check Foreign Keys
            for local_col, ref_table, ref_col in table_def.fk_constraints:
                # Local column exists
                if local_col.lower() not in table_def.columns:
                    errors.append(
                        ValidationErrorDetail(
                            code=ValidationErrorCode.INVALID_FK,
                            message=(
                                f"Foreign key column '{local_col}' does not exist in "
                                f"table '{table_def.name}'."
                            ),
                            location=f"Table '{table_def.name}', FK constraint",
                            severity="error",
                            suggested_fix="Ensure foreign key refers to a defined local column.",
                        )
                    )

                # Referenced table exists
                if ref_table.lower() not in tables:
                    errors.append(
                        ValidationErrorDetail(
                            code=ValidationErrorCode.INVALID_FK,
                            message=(
                                f"Foreign key refers to non-existent table '{ref_table}' "
                                f"from table '{table_def.name}'."
                            ),
                            location=f"Table '{table_def.name}', FK REFERENCES '{ref_table}'",
                            severity="error",
                            suggested_fix="Ensure referenced table is defined.",
                        )
                    )
                else:
                    # Referenced column exists in referenced table
                    ref_tbl_def = tables[ref_table.lower()]
                    if ref_col.lower() not in ref_tbl_def.columns:
                        errors.append(
                            ValidationErrorDetail(
                                code=ValidationErrorCode.INVALID_FK,
                                message=(
                                    f"Foreign key refers to non-existent column '{ref_col}' "
                                    f"in table '{ref_table}' from table '{table_def.name}'."
                                ),
                                location=(
                                    f"Table '{table_def.name}', FK REFERENCES "
                                    f"'{ref_table}({ref_col})'"
                                ),
                                severity="error",
                                suggested_fix=(
                                    f"Ensure the column '{ref_col}' exists in table '{ref_table}'."
                                ),
                            )
                        )

        return errors
