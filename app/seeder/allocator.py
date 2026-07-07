"""In-memory placeholder record allocator for synthetic data generation."""

import uuid
from typing import Any

from app.schemas.schema_design import SchemaModel


class RecordAllocator:
    """Allocates placeholder records for the generation pipeline."""

    @staticmethod
    def allocate(
        schema: SchemaModel, ordered_tables: list[str], row_targets: dict[str, int]
    ) -> dict[str, list[dict[str, Any]]]:
        """Allocate empty records for every table based on dependency ordering.

        Args:
            schema: The full schema model.
            ordered_tables: Topologically sorted list of table names.
            row_targets: Mapping of table name to target row count.

        Returns:
            Dictionary mapping table names to lists of allocated record placeholders.
        """
        table_map = {t.name: t for t in schema.tables}
        placeholders: dict[str, list[dict[str, Any]]] = {}

        for table_name in ordered_tables:
            target = row_targets.get(table_name, 0)
            table_obj = table_map.get(table_name)

            if not table_obj:
                continue

            columns = [col.name for col in table_obj.columns]

            table_records = []
            for i in range(target):
                record = {
                    "_ref_id": str(uuid.uuid4()),
                    "_table": table_name,
                    "_index": i,
                }
                # Initialize empty business fields
                for col in columns:
                    record[col] = None

                table_records.append(record)

            placeholders[table_name] = table_records

        return placeholders
