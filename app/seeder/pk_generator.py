"""Deterministic primary key generation for synthetic data records.

Introduces GlobalSequenceManager for global, batch-safe, parallel-safe
sequence allocation across all tables.
"""

import threading
import uuid
from typing import Any

from app.schemas.schema_design import SchemaModel


class GlobalSequenceManager:
    """Thread-safe global sequence counter for primary key generation.

    The sequence never restarts per table, ensuring global uniqueness
    across all integer primary keys in the dataset.
    """

    def __init__(self, start: int = 1) -> None:
        self._counter = start
        self._lock = threading.Lock()

    def next(self) -> int:
        with self._lock:
            value = self._counter
            self._counter += 1
            return value

    def allocate_batch(self, count: int) -> tuple[int, int]:
        """Allocate a contiguous block of sequence values.

        Returns:
            Tuple of (start, end) inclusive.
        """
        with self._lock:
            start = self._counter
            self._counter += count
            return start, self._counter - 1

    def peek(self) -> int:
        with self._lock:
            return self._counter

    def reset(self, value: int = 1) -> None:
        with self._lock:
            self._counter = value


class PrimaryKeyGenerator:
    """Generates deterministic primary keys for placeholder records.

    Uses GlobalSequenceManager to ensure globally unique integer PKs
    that never restart per table.
    """

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
            start_id: The initial value for the global sequence.
        """
        table_map = {t.name: t for t in schema.tables}
        sequence = GlobalSequenceManager(start=start_id)

        for table_name, records in placeholders.items():
            table_obj = table_map.get(table_name)
            if not table_obj:
                continue

            pk_columns = [col for col in table_obj.columns if col.is_primary_key]

            for pk_col in pk_columns:
                col_type = pk_col.type.lower()
                is_uuid = "uuid" in col_type or "guid" in col_type
                is_int = (
                    "int" in col_type
                    or "serial" in col_type
                    or "auto" in col_type
                    or col_type == "integer"
                    or col_type == "bigint"
                    or col_type == "smallint"
                )

                for record in records:
                    from app.seeder.lineage import LineageEngine

                    if is_uuid:
                        seq_val = sequence.next()
                        unique_name = f"{table_name}_{seq_val}"
                        record[pk_col.name] = str(
                            uuid.uuid5(uuid.NAMESPACE_OID, unique_name)
                        )
                        LineageEngine.record_origin(
                            record,
                            pk_col.name,
                            "PK Generated",
                            "Deterministic UUID based on table and global sequence.",
                        )
                    elif is_int:
                        pk_val = sequence.next()
                        record[pk_col.name] = pk_val
                        LineageEngine.record_origin(
                            record,
                            pk_col.name,
                            "PK Generated",
                            "Global sequence integer.",
                        )
                    else:
                        pk_val = sequence.next()
                        record[pk_col.name] = f"PK-{pk_val}"
                        LineageEngine.record_origin(
                            record,
                            pk_col.name,
                            "PK Generated",
                            "Fallback string from global sequence.",
                        )
