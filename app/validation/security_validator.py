"""Security validator verifying SQL DDL against injection and dangerous administrative commands."""

import re

from app.validation.validation_errors import ValidationErrorCode, ValidationErrorDetail

# Case-insensitive dangerous patterns matching whole words or exact phrases
DANGEROUS_PATTERNS = {
    r"\bDROP\b": "DROP commands are dangerous and strictly forbidden",
    r"\bDELETE\b": "DELETE statements are strictly forbidden",
    r"\bTRUNCATE\b": "TRUNCATE operations are strictly forbidden",
    r"\bALTER\b": "ALTER statements are forbidden to prevent schema modification",
    r"\bEXEC(?:UTE)?\b": "EXECUTE/EXEC statements are forbidden to prevent remote code execution",
    r"\bCALL\b": "CALL statements are forbidden to prevent stored procedure execution",
    r"\bCREATE\s+USER\b": "CREATE USER statements are forbidden to prevent privilege escalation",
    r"\bGRANT\b": "GRANT statements are forbidden to prevent privilege modification",
    r"\bREVOKE\b": "REVOKE statements are forbidden to prevent privilege modification",
    r"\bEXECUTE\s+IMMEDIATE\b": "Dynamic SQL execution is forbidden",
    r"\bsp_executesql\b": "Dynamic SQL execution is forbidden",
}


class SecurityValidator:
    """Security gate validator verifying that DDL contains no malicious payloads."""

    def validate(self, ddl: str) -> list[ValidationErrorDetail]:
        """Validate DDL text for security violations.

        Args:
            ddl: The raw SQL DDL string.

        Returns:
            List[ValidationErrorDetail]: List of security validation errors.
        """
        errors: list[ValidationErrorDetail] = []
        if not ddl.strip():
            return errors

        # 1. Check for suspicious payloads in comments
        # Extract comments: single-line (--) and multi-line (/* */)
        single_line_comments = re.findall(r"--.*", ddl)
        multi_line_comments = re.findall(r"/\*.*?\*/", ddl, re.DOTALL)

        all_comments = single_line_comments + multi_line_comments
        for comment in all_comments:
            # Check comments for dangerous keywords
            for pattern, msg in DANGEROUS_PATTERNS.items():
                if re.search(pattern, comment, re.IGNORECASE):
                    errors.append(
                        ValidationErrorDetail(
                            code=ValidationErrorCode.DANGEROUS_SQL,
                            message=f"Suspicious payload in SQL comment: {msg}",
                            location="SQL comment",
                            severity="error",
                            suggested_fix="Remove comments or dangerous commands within comments.",
                        )
                    )

        # 2. Check the entire DDL for dangerous keywords (ignoring comments to avoid duplicate hits)
        cleaned_ddl = re.sub(r"--.*", "", ddl)
        cleaned_ddl = re.sub(r"/\*.*?\*/", "", cleaned_ddl, flags=re.DOTALL)

        for pattern, msg in DANGEROUS_PATTERNS.items():
            if re.search(pattern, cleaned_ddl, re.IGNORECASE):
                # Find line number or approximate location
                match = re.search(pattern, cleaned_ddl, re.IGNORECASE)
                loc = f"Near keyword '{match.group(0)}'" if match else "DDL schema"
                errors.append(
                    ValidationErrorDetail(
                        code=ValidationErrorCode.DANGEROUS_SQL,
                        message=msg,
                        location=loc,
                        severity="error",
                        suggested_fix="Remove the forbidden keyword/operation.",
                    )
                )

        # 3. Check for multiple statements separated by semicolons (except CREATE TABLE/TYPE)
        # Split by semicolons and verify only supported commands are defined
        statements = [s.strip() for s in cleaned_ddl.split(";") if s.strip()]
        for stmt in statements:
            # Allow: CREATE TABLE, CREATE TYPE, CREATE ENUM, or standard DDL structure
            prefix_match = re.match(r"^\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)?)", stmt)
            if prefix_match:
                prefix = prefix_match.group(1).upper()
                if prefix not in ("CREATE TABLE", "CREATE TYPE", "CREATE ENUM"):
                    errors.append(
                        ValidationErrorDetail(
                            code=ValidationErrorCode.UNSUPPORTED_STATEMENT,
                            message=f"Unsupported statement prefix: '{prefix}'",
                            location=f"Statement: {stmt[:50]}...",
                            severity="error",
                            suggested_fix="Only CREATE TABLE and CREATE TYPE statements are allowed in DDL input.",
                        )
                    )

        return errors
