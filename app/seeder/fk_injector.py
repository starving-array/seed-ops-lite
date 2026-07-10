"""Foreign key injector to map relationships deterministically."""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.schemas.schema_design import SchemaModel

logger = logging.getLogger(__name__)


@dataclass
class InjectionStats:
    """Statistics for foreign key injection."""

    total_injected: int
    by_relationship: dict[str, int] = field(default_factory=dict)
    missing_src: int = 0
    missing_tgt: int = 0
    null_pk: int = 0
    ambiguous: int = 0


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

            src_col_id = rel.source_column_id
            tgt_col_id = rel.target_column_id

            src_col_name = col_id_to_name.get(src_col_id)
            tgt_col_name = col_id_to_name.get(tgt_col_id)

            if not src_col_name or not tgt_col_name:
                continue

            # Identify which is PK and which is FK
            src_is_pk = False
            tgt_is_pk = False
            for t in schema.tables:
                for c in t.columns:
                    if c.id == src_col_id and c.is_primary_key:
                        src_is_pk = True
                    if c.id == tgt_col_id and c.is_primary_key:
                        tgt_is_pk = True

            for src_ref_id, tgt_ref_ids in rel_map.items():
                src_record = ref_lookup.get(src_ref_id)
                if not src_record:
                    logger.warning(
                        "FK injection skipped: source ref %s not found for relationship %s",
                        src_ref_id,
                        rel.name,
                    )
                    stats.missing_src += 1
                    continue

                for tgt_ref_id in tgt_ref_ids:
                    tgt_record = ref_lookup.get(tgt_ref_id)
                    if not tgt_record:
                        logger.warning(
                            "FK injection skipped: target ref %s not found for relationship %s",
                            tgt_ref_id,
                            rel.name,
                        )
                        stats.missing_tgt += 1
                        continue

                    # If source is the parent (holds PK)
                    if src_is_pk:
                        parent_pk_value = src_record.get(src_col_name)
                        if parent_pk_value is not None:
                            tgt_record[tgt_col_name] = parent_pk_value
                            from app.seeder.lineage import LineageEngine

                            LineageEngine.record_origin(
                                tgt_record,
                                tgt_col_name,
                                "FK Injected",
                                f"Resolved from relationship {rel.name}.",
                            )
                            injections_for_rel += 1
                            stats.total_injected += 1
                        else:
                            logger.error(
                                "FK injection failed: null PK value for %s.%s (ref: %s) in relationship %s",
                                src_record.get("_table", "?"),
                                src_col_name,
                                src_ref_id,
                                rel.name,
                            )
                            stats.null_pk += 1

                    # If target is the parent (holds PK)
                    elif tgt_is_pk:
                        parent_pk_value = tgt_record.get(tgt_col_name)
                        if parent_pk_value is not None:
                            src_record[src_col_name] = parent_pk_value
                            from app.seeder.lineage import LineageEngine

                            LineageEngine.record_origin(
                                src_record,
                                src_col_name,
                                "FK Injected",
                                f"Resolved from relationship {rel.name}.",
                            )
                            injections_for_rel += 1
                            stats.total_injected += 1
                        else:
                            logger.error(
                                "FK injection failed: null PK value for %s.%s (ref: %s) in relationship %s",
                                tgt_record.get("_table", "?"),
                                tgt_col_name,
                                tgt_ref_id,
                                rel.name,
                            )
                            stats.null_pk += 1

                    else:
                        logger.warning(
                            "FK injection skipped: neither source nor target column is PK for relationship %s (src=%s, tgt=%s)",
                            rel.name,
                            src_col_name,
                            tgt_col_name,
                        )
                        stats.ambiguous += 1

            stats.by_relationship[rel.name] = injections_for_rel

        return stats
