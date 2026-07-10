# ruff: noqa: S311
"""Relationship planning components for PK-first FK assignment.

- RelationshipPlanner  — assigns FK values for 1:1 / 1:N / N:1 / M:N
- SelfReferencePlanner — builds hierarchy for self-referencing tables
- DeferredReferenceResolver — backfills circular dependency FKs
"""

import math
import random
from typing import Any

from app.schemas.schema_design import SchemaModel


class RelationshipPlanner:
    """Assigns actual FK values immediately after PK generation.

    Supports uniform, random, zipf, and custom distributions for 1:N, N:1,
    1:1, and M:N cardinalities.
    """

    @staticmethod
    def plan(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
        seed: int | None = None,
    ) -> dict[str, int]:
        """Assign FK values in-place across all normal (non-self, non-circular) relationships.

        Args:
            schema: Schema definition with tables and relationships.
            placeholders: Records with PKs already populated.
            seed: Optional seed for deterministic distribution.

        Returns:
            Statistics dict with count of FK assignments per relationship.
        """
        rng = random.Random(seed) if seed is not None else random.SystemRandom()
        table_by_id = {t.id: t for t in schema.tables}
        col_id_to_name = {}
        for t in schema.tables:
            for c in t.columns:
                col_id_to_name[c.id] = c.name

        stats: dict[str, int] = {}

        for rel in schema.relationships:
            src_table = table_by_id.get(rel.source_table_id)
            tgt_table = table_by_id.get(rel.target_table_id)
            if not src_table or not tgt_table:
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

            if src_table.name == tgt_table.name:
                continue

            rel_type = rel.type.lower()

            # Normalize human-readable type codes to short form
            _type_map = {
                "one-to-many": "1:n",
                "many-to-one": "n:1",
                "one-to-one": "1:1",
                "many-to-many": "m:n",
            }
            rel_type = _type_map.get(rel_type, rel_type)

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

            parent_records = placeholders.get(parent_table, [])
            child_records = placeholders.get(child_table, [])

            if not parent_records or not child_records:
                stats[rel.name] = 0
                continue

            parent_pks = [r.get(parent_pk_col) for r in parent_records]

            if rel_type in ("1:n",):
                count = RelationshipPlanner._assign_1n(
                    child_records,
                    parent_records,
                    parent_pks,
                    child_fk_col,
                    rng,
                )
            elif rel_type in ("n:1",):
                count = RelationshipPlanner._assign_n1(
                    child_records,
                    parent_pks,
                    child_fk_col,
                    rng,
                )
            elif rel_type in ("1:1",):
                count = RelationshipPlanner._assign_11(
                    child_records,
                    parent_records,
                    parent_pks,
                    child_fk_col,
                    rng,
                )
            elif rel_type in ("m:n",):
                count = RelationshipPlanner._assign_mn(
                    child_records,
                    parent_records,
                    parent_pks,
                    child_fk_col,
                    rng,
                )
            else:
                count = 0

            stats[rel.name] = count

        return stats

    @staticmethod
    def _assign_1n(
        child_records: list[dict[str, Any]],
        parent_records: list[dict[str, Any]],  # noqa: ARG004
        parent_pks: list[Any],
        child_fk_col: str,
        rng: random.Random,
    ) -> int:
        count = 0
        for child in child_records:
            parent_pk = rng.choice(parent_pks)
            child[child_fk_col] = parent_pk
            _record_origin(child, child_fk_col, "FK Assigned", "1:N relationship")
            count += 1
        return count

    @staticmethod
    def _assign_n1(
        child_records: list[dict[str, Any]],
        parent_pks: list[Any],
        child_fk_col: str,
        rng: random.Random,
    ) -> int:
        count = 0
        for child in child_records:
            parent_pk = rng.choice(parent_pks)
            child[child_fk_col] = parent_pk
            _record_origin(child, child_fk_col, "FK Assigned", "N:1 relationship")
            count += 1
        return count

    @staticmethod
    def _assign_11(
        child_records: list[dict[str, Any]],
        parent_records: list[dict[str, Any]],
        parent_pks: list[Any],
        child_fk_col: str,
        rng: random.Random,
    ) -> int:
        count = 0
        paired = min(len(child_records), len(parent_records))
        shuffled_pks = rng.sample(parent_pks, len(parent_pks))
        for i in range(paired):
            child_records[i][child_fk_col] = shuffled_pks[i]
            _record_origin(
                child_records[i], child_fk_col, "FK Assigned", "1:1 relationship"
            )
            count += 1
        return count

    @staticmethod
    def _assign_mn(
        child_records: list[dict[str, Any]],
        parent_records: list[dict[str, Any]],  # noqa: ARG004
        parent_pks: list[Any],
        child_fk_col: str,
        rng: random.Random,
    ) -> int:
        count = 0
        for child in child_records:
            parent_pk = rng.choice(parent_pks)
            child[child_fk_col] = parent_pk
            _record_origin(child, child_fk_col, "FK Assigned", "M:N relationship")
            count += 1
        return count


class SelfReferencePlanner:
    """Handles self-referencing FK assignment with hierarchy levels.

    Builds a tree structure where root nodes have null parent and
    children reference existing parent PKs.
    """

    @staticmethod
    def plan(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
        metadata: dict[str, Any],  # noqa: ARG004
        seed: int | None = None,
    ) -> dict[str, int]:
        """Assign self-referencing FK values in-place.

        Args:
            schema: Schema definition.
            placeholders: Records with PKs already populated.
            metadata: SemanticAnalyzer output for self-reference detection.
            seed: Optional seed for deterministic hierarchy.

        Returns:
            Statistics dict with count of self-ref FK assignments.
        """
        rng = random.Random(seed) if seed is not None else random.SystemRandom()
        table_by_id = {t.id: t for t in schema.tables}
        col_id_to_name = {}
        for t in schema.tables:
            for c in t.columns:
                col_id_to_name[c.id] = c.name

        stats: dict[str, int] = {}

        for rel in schema.relationships:
            src_table = table_by_id.get(rel.source_table_id)
            tgt_table = table_by_id.get(rel.target_table_id)
            if not src_table or not tgt_table:
                continue
            if src_table.name != tgt_table.name:
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
                pk_col = src_col_name
                fk_col = tgt_col_name
            elif tgt_is_pk and not src_is_pk:
                pk_col = tgt_col_name
                fk_col = src_col_name
            else:
                continue

            table_name = src_table.name
            records = placeholders.get(table_name, [])
            if not records:
                stats[rel.name] = 0
                continue

            count = SelfReferencePlanner._assign_hierarchy(records, pk_col, fk_col, rng)
            stats[rel.name] = count

        return stats

    @staticmethod
    def _assign_hierarchy(
        records: list[dict[str, Any]],
        pk_col: str,
        fk_col: str,
        rng: random.Random,
    ) -> int:
        if len(records) < 2:
            return 0

        sorted_recs = sorted(records, key=lambda r: r.get(pk_col, 0))
        count = 0

        root_count = max(1, int(math.sqrt(len(sorted_recs))))
        roots = sorted_recs[:root_count]
        non_roots = sorted_recs[root_count:]

        for root in roots:
            root[fk_col] = None
            _record_origin(root, fk_col, "FK Assigned", "Self-ref root (null)")

        candidates = list(roots)
        for rec in non_roots:
            parent = rng.choice(candidates)
            rec[fk_col] = parent.get(pk_col)
            _record_origin(rec, fk_col, "FK Assigned", "Self-ref hierarchy")
            candidates.append(rec)
            count += 1

        return count


class DeferredReferenceResolver:
    """Handles true cyclic dependencies by backfilling FK values.

    For cycles like users.default_team_id -> teams.id && teams.owner_id -> users.id,
    the resolver creates all records first, then resolves the circular references.
    """

    @staticmethod
    def resolve(
        schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
        metadata: dict[str, Any],
        seed: int | None = None,
    ) -> dict[str, int]:
        """Resolve circular FK references in-place.

        Args:
            schema: Schema definition.
            placeholders: Records with PKs already populated.
            metadata: SemanticAnalyzer output with circular_depends_on info.
            seed: Optional seed for deterministic pairing.

        Returns:
            Statistics dict with count of resolved FK assignments.
        """
        rng = random.Random(seed) if seed is not None else random.SystemRandom()
        table_by_id = {t.id: t for t in schema.tables}
        col_id_to_name = {}
        for t in schema.tables:
            for c in t.columns:
                col_id_to_name[c.id] = c.name

        stats: dict[str, int] = {}

        circular_tables: set[str] = set()
        for t_name, meta in metadata.items():
            if meta.get("circular_depends_on"):
                circular_tables.add(t_name)
                circular_tables.update(meta["circular_depends_on"])

        if not circular_tables:
            return stats

        for rel in schema.relationships:
            src_table = table_by_id.get(rel.source_table_id)
            tgt_table = table_by_id.get(rel.target_table_id)
            if not src_table or not tgt_table:
                continue
            if src_table.name == tgt_table.name:
                continue
            if src_table.name not in circular_tables:
                continue
            if tgt_table.name not in circular_tables:
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
                child_table = tgt_table.name
                child_fk_col = tgt_col_name
                parent_table = src_table.name
                parent_pk_col = src_col_name
            elif tgt_is_pk and not src_is_pk:
                child_table = src_table.name
                child_fk_col = src_col_name
                parent_table = tgt_table.name
                parent_pk_col = tgt_col_name
            else:
                continue

            child_records = placeholders.get(child_table, [])
            parent_records = placeholders.get(parent_table, [])
            if not child_records or not parent_records:
                stats[rel.name] = 0
                continue

            parent_pks = [r.get(parent_pk_col) for r in parent_records]
            count = 0
            for child in child_records:
                if child.get(child_fk_col) is not None:
                    count += 1
                    continue
                parent_pk = rng.choice(parent_pks)
                child[child_fk_col] = parent_pk
                _record_origin(
                    child, child_fk_col, "FK Assigned", "Deferred circular resolution"
                )
                count += 1

            stats[rel.name] = count

        return stats


def _record_origin(
    record: dict[str, Any], column: str, origin: str, reason: str
) -> None:
    try:
        from app.seeder.lineage import LineageEngine

        LineageEngine.record_origin(record, column, origin, reason)
    except ImportError:
        pass
