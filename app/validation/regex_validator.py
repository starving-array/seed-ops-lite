"""Lexical validator validating parenthesis matching, reserved words, and empty schema."""

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
}


class RegexValidator:
    """Lexical validator validating parenthesis matching, reserved words, and empty schema."""

    def validate(self, ddl: str) -> list[ValidationErrorDetail]:
        """Validate DDL text for lexical and structural regex checks.

        Args:
            ddl: The raw SQL DDL string.

        Returns:
            List[ValidationErrorDetail]: List of validation errors.
        """
        errors: list[ValidationErrorDetail] = []
        stripped = ddl.strip()

        # 1. Empty input validation
        if not stripped:
            errors.append(
                ValidationErrorDetail(
                    code=ValidationErrorCode.EMPTY_SCHEMA,
                    message="Schema input is empty",
                    location="Root",
                    severity="error",
                    suggested_fix="Provide a valid SQL CREATE TABLE DDL schema.",
                )
            )
            return errors

        # 2. Match Parentheses check
        open_count = stripped.count("(")
        close_count = stripped.count(")")
        if open_count != close_count:
            errors.append(
                ValidationErrorDetail(
                    code=ValidationErrorCode.MALFORMED_DDL,
                    message=f"Unmatched parentheses. Open: {open_count}, Close: {close_count}",
                    location="Entire DDL",
                    severity="error",
                    suggested_fix="Ensure every opening parenthesis '(' has a matching closing parenthesis ')'.",
                )
            )

        # 3. Match Quotes check (single and double quotes)
        single_quotes = stripped.count("'")
        double_quotes = stripped.count('"')
        if single_quotes % 2 != 0:
            errors.append(
                ValidationErrorDetail(
                    code=ValidationErrorCode.MALFORMED_DDL,
                    message="Unmatched single quotes (') found in DDL.",
                    location="Entire DDL",
                    severity="error",
                    suggested_fix="Ensure all literal strings have matching single quotes.",
                )
            )
        if double_quotes % 2 != 0:
            errors.append(
                ValidationErrorDetail(
                    code=ValidationErrorCode.MALFORMED_DDL,
                    message='Unmatched double quotes (") found in DDL.',
                    location="Entire DDL",
                    severity="error",
                    suggested_fix="Ensure all quoted identifiers have matching double quotes.",
                )
            )

        # 4. Reserved keywords checks in table names
        cleaned = re.sub(r"--.*", "", stripped)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

        table_matches = re.finditer(
            r"\bCREATE\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", cleaned, re.IGNORECASE
        )
        for match in table_matches:
            tbl_name = match.group(1)
            if tbl_name.upper() in RESERVED_KEYWORDS:
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.RESERVED_KEYWORD,
                        message=f"Reserved SQL keyword '{tbl_name}' used as table name.",
                        location=f"Table '{tbl_name}'",
                        severity="error",
                        suggested_fix=f"Rename the table '{tbl_name}' to a non-reserved word.",
                    )
                )

        return errors
