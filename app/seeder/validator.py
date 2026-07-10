"""Data validation engine for generated synthetic records."""

import datetime
import re
import uuid
from typing import Any

from app.schemas.schema_design import SchemaModel
from app.seeder.models import FieldDefinition


class SeederValidator:
    """Validator to ensure all generated records adhere to the specifications."""

    @staticmethod
    def validate_record(
        record_data: dict[str, Any], fields: dict[str, FieldDefinition]
    ) -> list[str]:
        """Validate a single record against the requested fields schema.

        Args:
            record_data: The dictionary containing generated field values.
            fields: The schema field definitions.

        Returns:
            list[str]: List of validation error messages.
        """
        errors = []

        for field_name, field_def in fields.items():
            # 1. Required Check
            if field_name not in record_data or record_data[field_name] is None:
                if field_def.required:
                    errors.append(
                        f"Field '{field_name}' is required but was missing or null."
                    )
                continue

            value = record_data[field_name]
            field_type = field_def.type.lower()
            rules = field_def.rules or {}

            # 2. Type and rule validation
            if field_type == "uuid":
                try:
                    uuid.UUID(str(value))
                except ValueError:
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not a valid UUID."
                    )

            elif field_type == "id":
                if not isinstance(value, int):
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        errors.append(
                            f"Field '{field_name}' value '{value}' is not a valid integer ID."
                        )

            elif field_type == "date":
                date_format = rules.get("format", "%Y-%m-%dT%H:%M:%S")
                if date_format == "iso":
                    try:
                        datetime.datetime.fromisoformat(str(value))
                    except ValueError:
                        errors.append(
                            f"Field '{field_name}' value '{value}' is not a valid ISO 8601 date string."
                        )
                else:
                    try:
                        datetime.datetime.strptime(str(value), date_format)
                    except ValueError:
                        errors.append(
                            f"Field '{field_name}' value '{value}' does not match format '{date_format}'."
                        )

            elif field_type == "boolean":
                if not isinstance(value, bool) and str(value).lower() not in [
                    "true",
                    "false",
                    "1",
                    "0",
                ]:
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not a valid boolean."
                    )

            elif field_type == "enum":
                allowed_values = rules.get("values", [])
                if allowed_values and value not in allowed_values:
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not in allowed enum values {allowed_values}."
                    )

            elif field_type == "numeric_range":
                try:
                    num_val = float(value)
                    min_val = rules.get("min")
                    max_val = rules.get("max")
                    if min_val is not None and num_val < float(min_val):
                        errors.append(
                            f"Field '{field_name}' value {num_val} is less than minimum {min_val}."
                        )
                    if max_val is not None and num_val > float(max_val):
                        errors.append(
                            f"Field '{field_name}' value {num_val} is greater than maximum {max_val}."
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"Field '{field_name}' value '{value}' is not a valid number."
                    )

            elif field_type == "rule_based":
                pattern = rules.get("pattern")
                if pattern:
                    try:
                        if not re.match(pattern, str(value)):
                            errors.append(
                                f"Field '{field_name}' value '{value}' does not match pattern '{pattern}'."
                            )
                    except re.error:
                        pass

            # AI semantic types
            elif field_type in [
                "name",
                "address",
                "biography",
                "description",
                "free_text",
                "domain_content",
            ]:
                if not isinstance(value, str):
                    errors.append(
                        f"Field '{field_name}' value must be a string (got {type(value).__name__})."
                    )
                elif not value.strip():
                    errors.append(
                        f"Field '{field_name}' value must be a non-empty string."
                    )
                else:
                    min_len = rules.get("min_length")
                    max_len = rules.get("max_length")
                    if min_len is not None and len(value) < int(min_len):
                        errors.append(
                            f"Field '{field_name}' length {len(value)} is less than min_length {min_len}."
                        )
                    if max_len is not None and len(value) > int(max_len):
                        errors.append(
                            f"Field '{field_name}' length {len(value)} is greater than max_length {max_len}."
                        )

        return errors

    @staticmethod
    def validate_referential_integrity(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Validate that every FK value references an existing PK in the parent table.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        table_by_id = {t.id: t for t in schema.tables}
        col_id_to_name = {}
        for t in schema.tables:
            for c in t.columns:
                col_id_to_name[c.id] = c.name

        for rel in schema.relationships:
            src_table = table_by_id.get(rel.source_table_id)
            tgt_table = table_by_id.get(rel.target_table_id)
            if not src_table or not tgt_table:
                continue
            if src_table.name == tgt_table.name:
                continue

            src_col_name = col_id_to_name.get(rel.source_column_id)
            tgt_col_name = col_id_to_name.get(rel.target_column_id)
            if not src_col_name or not tgt_col_name:
                continue

            src_is_pk = any(
                c.id == rel.source_column_id and c.is_primary_key
                for c in src_table.columns
            )
            tgt_is_pk = any(
                c.id == rel.target_column_id and c.is_primary_key
                for c in tgt_table.columns
            )

            if src_is_pk and not tgt_is_pk:
                parent_table = src_table.name
                parent_pk_col = src_col_name
                child_table = tgt_table.name
                child_fk_col = tgt_col_name
            elif tgt_is_pk and not src_is_pk:
                parent_table = tgt_table.name
                parent_pk_col = tgt_col_name
                child_table = src_table.name
                child_fk_col = src_col_name
            elif src_is_pk and tgt_is_pk:
                parent_table = src_table.name
                parent_pk_col = src_col_name
                child_table = tgt_table.name
                child_fk_col = tgt_col_name
            else:
                continue

            parent_pks = {
                r.get(parent_pk_col)
                for r in placeholders.get(parent_table, [])
                if r.get(parent_pk_col) is not None
            }

            for rec in placeholders.get(child_table, []):
                fk_val = rec.get(child_fk_col)
                if fk_val is not None and fk_val not in parent_pks:
                    ref_id = rec.get("_ref_id", "?")
                    errors.append(
                        f"Referential integrity violation: {child_table}.{child_fk_col}"
                        f" = {fk_val} not found in {parent_table}.{parent_pk_col}"
                        f" (ref: {ref_id}, relationship: {rel.name})"
                    )

        return errors

    @staticmethod
    def validate_pk_uniqueness(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Validate that PK values are unique within each table.

        Only single-column PKs are checked; composite PKs may have duplicate
        values in individual columns (uniqueness is on the pair).
        Use validate_junction_uniqueness for composite PKs.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        table_pk_cols: dict[str, list[str]] = {}
        for t in schema.tables:
            table_pk_cols[t.name] = [c.name for c in t.columns if c.is_primary_key]

        for table_name, records in placeholders.items():
            pk_cols = table_pk_cols.get(table_name, [])
            if not pk_cols or len(pk_cols) > 1:
                continue

            seen: set[Any] = set()
            col = pk_cols[0]
            for rec in records:
                val = rec.get(col)
                if val is not None and val in seen:
                    errors.append(
                        f"PK uniqueness violation: {table_name}.{col}"
                        f" = {val} is duplicated"
                    )
                if val is not None:
                    seen.add(val)
        return errors

    @staticmethod
    def validate_self_references(
        placeholders: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Validate that self-referencing FK values don't point to the same record.

        Detects columns where a FK value equals the record's own PK value
        (e.g. manager_id == employee_id for the same record).

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        for table_name, records in placeholders.items():
            for rec in records:
                pk_cols = [
                    k for k in rec if not k.startswith("_") and k != "manager_id"
                ]
                pk_val = None
                for pc in pk_cols:
                    v = rec.get(pc)
                    if v is not None:
                        pk_val = v
                        break

                for fk_col in (
                    "manager_id",
                    "reports_to",
                    "parent_id",
                    "supervisor_id",
                ):
                    if fk_col in rec:
                        fk_val = rec[fk_col]
                        if (
                            fk_val is not None
                            and pk_val is not None
                            and fk_val == pk_val
                        ):
                            ref_id = rec.get("_ref_id", "?")
                            errors.append(
                                f"Self-reference violation: {table_name}.{fk_col}"
                                f" = {fk_val} equals PK {pk_val}"
                                f" (ref: {ref_id})"
                            )

        return errors

    @staticmethod
    def validate_junction_uniqueness(
        placeholders: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Validate that junction table row pairs are unique.

        A junction table is detected by having a composite key pattern
        where all PK columns are also FK columns.

        Returns:
            List of validation error messages.
        """
        errors: list[str] = []
        for table_name, records in placeholders.items():
            cols = [k for k in (records[0] if records else {}) if not k.startswith("_")]
            pk_candidates = [c for c in cols if c.endswith("_id")]
            if len(pk_candidates) < 2:
                continue

            seen_pairs: set[tuple[Any, ...]] = set()
            for rec in records:
                pair = tuple(rec.get(c) for c in pk_candidates)
                if all(v is not None for v in pair):
                    if pair in seen_pairs:
                        errors.append(
                            f"Junction uniqueness violation: {table_name}"
                            f" duplicate pair {dict(zip(pk_candidates, pair, strict=False))}"
                        )
                    seen_pairs.add(pair)

        return errors
