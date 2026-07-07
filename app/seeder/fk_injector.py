"""Foreign key injector to map relationships deterministically."""

from dataclasses import dataclass
from typing import Any

from app.schemas.schema_design import SchemaModel


@dataclass
class InjectionStats:
    """Statistics for foreign key injection."""

    total_injected: int
    by_relationship: dict[str, int]


class ForeignKeyInjector:
    """Injects foreign keys into placeholder records based on the relationship map."""

    @staticmethod
    def inject(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
        relationship_map: dict[str, dict[str, list[str]]],
    ) -> InjectionStats:
        """Inject foreign keys into child records.

        Args:
            schema: Schema definition containing columns and relationships.
            placeholders: Dictionary mapping table name to a list of records.
            relationship_map: Relationship mapping from source _ref_id to target _ref_ids.

        Returns:
            InjectionStats containing total injections and breakdown by relationship.
        """
        stats = InjectionStats(total_injected=0, by_relationship={})

        # Build a fast lookup map for all records: _ref_id -> record dict
        ref_lookup: dict[str, dict[str, Any]] = {}
        for records in placeholders.values():
            for record in records:
                ref_id = record.get("_ref_id")
                if ref_id:
                    ref_lookup[ref_id] = record

        col_id_to_name = {}
        for t in schema.tables:
            for c in t.columns:
                col_id_to_name[c.id] = c.name

        for rel in schema.relationships:
            if rel.name not in relationship_map:
                continue

            rel_map = relationship_map[rel.name]
            injections_for_rel = 0

            # In our modeling, Source is the Parent (holds PK) and Target is the Child (holds FK)
            src_col_name = col_id_to_name.get(rel.source_column_id)
            tgt_col_name = col_id_to_name.get(rel.target_column_id)

            if not src_col_name or not tgt_col_name:
                continue

            for src_ref_id, tgt_ref_ids in rel_map.items():
                src_record = ref_lookup.get(src_ref_id)
                if not src_record:
                    continue

                parent_pk_value = src_record.get(src_col_name)
                if parent_pk_value is None:
                    continue

                for tgt_ref_id in tgt_ref_ids:
                    tgt_record = ref_lookup.get(tgt_ref_id)
                    if not tgt_record:
                        continue

                    # Inject the foreign key
                    tgt_record[tgt_col_name] = parent_pk_value
                    injections_for_rel += 1
                    stats.total_injected += 1

            stats.by_relationship[rel.name] = injections_for_rel

        return stats
