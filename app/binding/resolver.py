"""Relationship resolver parsing DDL, establishing topological order, and resolving FK maps."""

import re
from typing import Any

from app.agents.guardian.dependency_graph import DependencyGraph
from app.binding.exceptions import DependencyResolutionException
from app.binding.models import RelationshipReference, RelationshipType
from app.validation.ddl_validator import DDLValidator


class RelationshipResolver:
    """Resolves foreign key relationships on generated record sets based on database schema."""

    def __init__(self) -> None:
        """Initialize RelationshipResolver."""
        pass

    def get_relationship_references(
        self,
        schema_ddl: str,
        manual_relationships: dict[str, list[RelationshipReference]] | None = None,
    ) -> tuple[list[str], dict[str, list[RelationshipReference]]]:
        """Parse schema DDL to extract tables, resolve topological sort order, and map relationships.

        Args:
            schema_ddl: SQL schema DDL text.
            manual_relationships: Optional dict of custom relation references by table.

        Returns:
            Tuple[list[str], dict[str, list[RelationshipReference]]]:
                (ordered_tables, map of table name -> list of foreign key references)
        """
        ddl_validator = DDLValidator()
        ddl_validator.validate(schema_ddl)
        parsed_tables = ddl_validator.last_parsed_tables

        if not parsed_tables:
            raise DependencyResolutionException(
                "No tables found in the provided DDL schema."
            )

        # Build dependency graph
        graph = DependencyGraph()
        declared_tables = set()

        for _, table_def in parsed_tables.items():
            declared_tables.add(table_def.name)
            graph.add_node(table_def.name)
            for _, ref_table, _ in table_def.fk_constraints:
                graph.add_edge(ref_table, table_def.name)

        # Validate references
        graph.validate_dependencies(declared_tables)

        # Resolve order
        ordered_tables, _, _ = graph.get_topological_sort_and_layers()

        # Map relationships (FK constraints)
        relationships: dict[str, list[RelationshipReference]] = {}

        # Clean comments to search column definitions for UNIQUE keywords
        cleaned_ddl = re.sub(r"--.*", "", schema_ddl)
        cleaned_ddl = re.sub(r"/\*.*?\*/", "", cleaned_ddl, flags=re.DOTALL)

        for _, table_def in parsed_tables.items():
            table_name = table_def.name
            local_refs = []

            # Find the block of DDL for this specific table to restrict unique constraint checks
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

            # Determine column definition unique constraints
            unique_cols = set()
            for _, col_def in table_def.columns.items():
                col_name = col_def.name
                if col_name in table_def.pk_columns:
                    unique_cols.add(col_name.lower())

                col_regex = rf"\b{re.escape(col_name)}\b.*?\bUNIQUE\b"
                if table_block and re.search(col_regex, table_block, re.IGNORECASE):
                    unique_cols.add(col_name.lower())

            # Map constraints
            for local_col, ref_table, ref_col in table_def.fk_constraints:
                rel_type = RelationshipType.MANY_TO_ONE
                if local_col.lower() in unique_cols:
                    rel_type = RelationshipType.ONE_TO_ONE

                local_refs.append(
                    RelationshipReference(
                        local_column=local_col,
                        referenced_table=ref_table,
                        referenced_column=ref_col,
                        relationship_type=rel_type,
                    )
                )

            # Apply manual relationship overrides if defined
            if manual_relationships and table_name in manual_relationships:
                overrides = manual_relationships[table_name]
                override_map = {ov.local_column.lower(): ov for ov in overrides}
                merged_refs = []
                for ref in local_refs:
                    if ref.local_column.lower() in override_map:
                        merged_refs.append(override_map[ref.local_column.lower()])
                    else:
                        merged_refs.append(ref)

                parsed_cols = {ref.local_column.lower() for ref in local_refs}
                for ref in overrides:
                    if ref.local_column.lower() not in parsed_cols:
                        merged_refs.append(ref)
                local_refs = merged_refs

            relationships[table_name] = local_refs

        return ordered_tables, relationships

    def resolve_relationships(
        self,
        records: dict[str, list[dict[str, Any]]],
        ordered_tables: list[str],
        relationships: dict[str, list[RelationshipReference]],
    ) -> tuple[dict[str, list[dict[str, Any]]], int]:
        """Resolve and bind keys sequentially through the topological table list.

        Args:
            records: Dict mapping table names to generated list of record dicts.
            ordered_tables: Topologically sorted list of table names.
            relationships: Dict mapping table name -> list of RelationshipReferences.

        Returns:
            Tuple[dict[str, list[dict[str, Any]]], int]:
                (bound_records, count of unresolved references detected)
        """
        # Create a mutable copy of the records
        resolved_records = {
            tbl: [dict(rec) for rec in rec_list] for tbl, rec_list in records.items()
        }
        resolved_records_lower = {
            tbl.lower(): rec_list for tbl, rec_list in resolved_records.items()
        }

        unresolved_count = 0
        assigned_one_to_one: dict[str, set[Any]] = {}

        for table_lower in ordered_tables:
            table_records = resolved_records_lower.get(table_lower, [])
            if not table_records:
                continue

            table_relationships: list[RelationshipReference] = []
            for t_name, refs in relationships.items():
                if t_name.lower() == table_lower:
                    table_relationships = refs
                    break

            for ref in table_relationships:
                local_col = ref.local_column
                parent_table = ref.referenced_table
                parent_col = ref.referenced_column
                rel_type = ref.relationship_type

                parent_records = resolved_records_lower.get(parent_table.lower(), [])
                if not parent_records:
                    unresolved_count += len(table_records)
                    for rec in table_records:
                        matched_col = None
                        for k in rec:
                            if k.lower() == local_col.lower():
                                matched_col = k
                                break
                        if matched_col:
                            rec[matched_col] = None
                        else:
                            rec[local_col] = None
                    continue

                parent_keys = []
                for p_rec in parent_records:
                    pkey_val = None
                    for k, v in p_rec.items():
                        if k.lower() == parent_col.lower():
                            pkey_val = v
                            break
                    if pkey_val is not None:
                        parent_keys.append(pkey_val)

                if not parent_keys:
                    unresolved_count += len(table_records)
                    for rec in table_records:
                        matched_col = None
                        for k in rec:
                            if k.lower() == local_col.lower():
                                matched_col = k
                                break
                        if matched_col:
                            rec[matched_col] = None
                        else:
                            rec[local_col] = None
                    continue

                one_to_one_key = f"{parent_table.lower()}.{parent_col.lower()}"
                if one_to_one_key not in assigned_one_to_one:
                    assigned_one_to_one[one_to_one_key] = set()

                for idx, rec in enumerate(table_records):
                    matched_col = None
                    for k in rec:
                        if k.lower() == local_col.lower():
                            matched_col = k
                            break
                    target_col = matched_col if matched_col else local_col

                    if rel_type == RelationshipType.ONE_TO_ONE:
                        assigned_set = assigned_one_to_one[one_to_one_key]
                        chosen_key = None
                        for p_key in parent_keys:
                            if p_key not in assigned_set:
                                chosen_key = p_key
                                break

                        if chosen_key is not None:
                            rec[target_col] = chosen_key
                            assigned_set.add(chosen_key)
                        else:
                            rec[target_col] = None
                            unresolved_count += 1
                    else:
                        chosen_key = parent_keys[idx % len(parent_keys)]
                        rec[target_col] = chosen_key

        return resolved_records, unresolved_count
