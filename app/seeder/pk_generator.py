"""Deterministic primary key generation for synthetic data records."""

import uuid
from typing import Any

from app.schemas.schema_design import SchemaModel


class PrimaryKeyGenerator:
    """Generates deterministic primary keys for placeholder records based on column definitions."""

    @staticmethod
    def generate(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
        start_id: int = 1,
    ) -> None:
        """In-place update of placeholder records with generated primary keys.

        Args:
            schema: The schema containing primary key column definitions.
            placeholders: Dictionary mapping table name to a list of records.
            start_id: The starting sequence for auto-increment / integer keys.
        """
        table_map = {t.name: t for t in schema.tables}

        for table_name, records in placeholders.items():
            table_obj = table_map.get(table_name)
            if not table_obj:
                continue

            # Identify primary key columns for this table
            pk_columns = [col for col in table_obj.columns if col.is_primary_key]

            for pk_col in pk_columns:
                col_type = pk_col.type.lower()
                is_uuid = "uuid" in col_type or "guid" in col_type
                is_int = "int" in col_type or "serial" in col_type or "auto" in col_type

                current_id = start_id

                for record in records:
                    if is_uuid:
                        # Generate deterministic UUID based on table and sequential index
                        unique_name = f"{table_name}_{current_id}"
                        record[pk_col.name] = str(
                            uuid.uuid5(uuid.NAMESPACE_OID, unique_name)
                        )
                    elif is_int:
                        # Auto increment / Integer
                        record[pk_col.name] = current_id
                    else:
                        # Fallback for unrecognized types
                        record[pk_col.name] = f"PK-{current_id}"

                    current_id += 1
