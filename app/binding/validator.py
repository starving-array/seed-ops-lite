"""Referential integrity validator verifying relationship bindings and detecting orphans."""

import re
from typing import Any

from app.binding.models import RelationshipReference
from app.validation.ddl_validator import DDLValidator


class ReferentialValidator:
    """Validator ensuring that foreign key references exist and are valid across datasets."""

    def __init__(self) -> None:
        """Initialize ReferentialValidator."""
        pass

    def validate(
        self,
        records: dict[str, list[dict[str, Any]]],
        schema_ddl: str,
        relationships: dict[str, list[RelationshipReference]],
    ) -> list[str]:
        """Verify referential integrity constraints.

        Args:
            records: Dict mapping table names to lists of record dicts.
            schema_ddl: SQL schema DDL text.
            relationships: Resolved table relationships map.

        Returns:
            list[str]: Detailed validation error messages.
        """
        errors = []

        ddl_validator = DDLValidator()
        ddl_validator.validate(schema_ddl)
        parsed_tables = ddl_validator.last_parsed_tables

        # Create a lowercase map for records lookup
        records_lower = {k.lower(): v for k, v in records.items()}

        # 1. First build a lookup map of all generated parent key values
        parent_keys_cache: dict[str, dict[str, set[Any]]] = {}

        for table_name_lower, table_records in records_lower.items():
            parent_keys_cache[table_name_lower] = {}
            if not table_records:
                continue

            first_rec = table_records[0]
            for col_name in first_rec:
                col_lower = col_name.lower()
                vals = set()
                for rec in table_records:
                    val = None
                    for k, v in rec.items():
                        if k.lower() == col_lower:
                            val = v
                            break
                    if val is not None:
                        vals.add(val)
                parent_keys_cache[table_name_lower][col_lower] = vals

        # 2. Perform FK check for each table in relationships
        for table_name, table_relationships in relationships.items():
            table_lower = table_name.lower()
            table_records = records_lower.get(table_lower, [])
            if not table_records:
                continue

            parsed_table_def = parsed_tables.get(table_lower)
            required_cols: set[str] = set()
            if parsed_table_def:
                required_cols.update(c.lower() for c in parsed_table_def.pk_columns)

                # Check DDL definitions for NOT NULL
                cleaned_ddl = re.sub(r"--.*", "", schema_ddl)
                cleaned_ddl = re.sub(r"/\*.*?\*/", "", cleaned_ddl, flags=re.DOTALL)
                table_block = ""
                match_tbl = re.search(
                    rf"\bCREATE\s+TABLE\s+{re.escape(table_name)}\b.*?\((.*?)\);",
                    cleaned_ddl,
                    re.IGNORECASE | re.DOTALL,
                )
                if match_tbl:
                    table_block = match_tbl.group(0)
                else:
                    match_tbl = re.search(
                        rf"\bCREATE\s+TABLE\s+{re.escape(table_name)}\b.*?\((.*?)\)",
                        cleaned_ddl,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if match_tbl:
                        table_block = match_tbl.group(0)

                for _, col_def in parsed_table_def.columns.items():
                    col_name = col_def.name
                    col_regex = rf"\b{re.escape(col_name)}\b.*?\bNOT\s+NULL\b"
                    target_text = table_block if table_block else cleaned_ddl
                    if re.search(col_regex, target_text, re.IGNORECASE):
                        required_cols.add(col_name.lower())

            for ref in table_relationships:
                local_col = ref.local_column
                parent_table = ref.referenced_table
                parent_col = ref.referenced_column

                parent_table_lower = parent_table.lower()
                parent_col_lower = parent_col.lower()

                parent_keys = parent_keys_cache.get(parent_table_lower, {}).get(
                    parent_col_lower, set()
                )

                is_required = local_col.lower() in required_cols

                for idx, rec in enumerate(table_records):
                    val = None
                    for k, v in rec.items():
                        if k.lower() == local_col.lower():
                            val = v
                            break

                    if val is None or str(val).strip() == "":
                        if is_required:
                            errors.append(
                                f"Required reference violation: Local required column '{local_col}' in "
                                f"child table '{table_name}' (Record index {idx}) is null or missing."
                            )
                    elif val not in parent_keys:
                        errors.append(
                            f"Referential integrity violation: Child table '{table_name}' column "
                            f"'{local_col}' (Record index {idx}) has orphan value '{val}' referencing "
                            f"non-existent parent key in table '{parent_table}' column '{parent_col}'."
                        )

        return errors
