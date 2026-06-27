"""Deterministic schema hashing implementation using SHA-256."""

import hashlib
import re


def extract_enum_definitions(ddl: str) -> list[str]:
    """Extract enum definitions and check in constraints from DDL text.

    Args:
        ddl: The SQL DDL string.

    Returns:
        list[str]: Sorted list of enum definition substrings.
    """
    # Clean comments
    cleaned = re.sub(r"--.*", "", ddl)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

    enums = []
    # 1. Postgres-style custom types: CREATE TYPE <name> AS ENUM (...)
    type_matches = re.finditer(
        r"\bCREATE\s+TYPE\s+\w+\s+AS\s+ENUM\s*\((.*?)\)",
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    for match in type_matches:
        enums.append(match.group(0).strip().lower())

    # 2. Check IN constraints: CHECK (col IN ('a', 'b'))
    check_matches = re.finditer(
        r"\bCHECK\s*\((.*?)\bIN\s*\((.*?)\)\)", cleaned, re.IGNORECASE | re.DOTALL
    )
    for match in check_matches:
        enums.append(match.group(0).strip().lower())

    return sorted(enums)


def generate_schema_hash(
    ddl: str, enums: list[str], validator_version: str, schema_hash_version: str
) -> str:
    """Generate a deterministic SHA-256 hash for a given DDL schema.

    Args:
        ddl: SQL DDL schema text.
        enums: Sorted list of enum definitions.
        validator_version: Version of the validation engine.
        schema_hash_version: Version of the schema hash format.

    Returns:
        str: SHA-256 hex digest of the normalized input values.
    """
    normalized_ddl = ddl.strip()
    normalized_enums = "|".join(enums)

    payload = (
        f"{normalized_ddl}:{normalized_enums}:{validator_version}:{schema_hash_version}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
