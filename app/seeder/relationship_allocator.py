# ruff: noqa: S311
"""In-memory relationship allocator mapping references between placeholder records."""

import random
from collections import defaultdict
from typing import Any

from app.schemas.schema_design import SchemaModel


class RelationshipAllocator:
    """Allocates relationships between placeholders using the schema graph."""

    @staticmethod
    def allocate(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
        seed: int | None = None,
    ) -> dict[str, dict[str, list[str]]]:
        """Allocate relationship mappings between records.

        Args:
            schema: The schema containing relationships.
            placeholders: Allocated placeholders generated previously.
            seed: Optional seed for deterministic behavior.

        Returns:
            A dictionary mapping Relationship Name to a dictionary of Source _ref_id -> List of Target _ref_ids.
        """
        rng = random.Random(seed) if seed is not None else random.SystemRandom()

        table_id_to_name = {t.id: t.name for t in schema.tables}
        relationship_map: dict[str, dict[str, list[str]]] = {}

        for rel in schema.relationships:
            rel_map: dict[str, list[str]] = defaultdict(list)

            src_table = table_id_to_name.get(rel.source_table_id)
            tgt_table = table_id_to_name.get(rel.target_table_id)

            if not src_table or not tgt_table:
                relationship_map[rel.name] = dict(rel_map)
                continue

            src_records = placeholders.get(src_table, [])
            tgt_records = placeholders.get(tgt_table, [])

            if not src_records or not tgt_records:
                relationship_map[rel.name] = dict(rel_map)
                continue

            rel_type = rel.type.lower()

            if rel_type == "1:n":
                # 1:N - Each target must have one source
                for tgt in tgt_records:
                    src = rng.choice(src_records)
                    rel_map[src["_ref_id"]].append(tgt["_ref_id"])

            elif rel_type == "n:1":
                # N:1 - Each source must have one target
                for src in src_records:
                    tgt = rng.choice(tgt_records)
                    rel_map[src["_ref_id"]].append(tgt["_ref_id"])

            elif rel_type == "1:1":
                # 1:1 - One source exactly matches one target
                paired_count = min(len(src_records), len(tgt_records))
                src_shuffled = rng.sample(src_records, len(src_records))
                tgt_shuffled = rng.sample(tgt_records, len(tgt_records))

                for i in range(paired_count):
                    rel_map[src_shuffled[i]["_ref_id"]].append(
                        tgt_shuffled[i]["_ref_id"]
                    )

            elif rel_type == "m:n":
                # M:N - Assign multiple targets to multiple sources
                num_connections = max(len(src_records), len(tgt_records)) * 2
                for _ in range(num_connections):
                    src = rng.choice(src_records)
                    tgt = rng.choice(tgt_records)
                    if tgt["_ref_id"] not in rel_map[src["_ref_id"]]:
                        rel_map[src["_ref_id"]].append(tgt["_ref_id"])

            relationship_map[rel.name] = dict(rel_map)

        return relationship_map
