"""Semantic Dependency Analyzer for Database Schemas."""

from typing import Any

from app.agents.guardian.dependency_graph import DependencyGraph
from app.schemas.schema_design import SchemaModel, TableModel


class SemanticAnalyzer:
    """Analyzes table columns to discover semantic classifications and dependencies."""

    @staticmethod
    def analyze(schema: SchemaModel) -> dict[str, Any]:
        """Produce semantic metadata for all tables in the schema."""
        metadata = {}
        for table in schema.tables:
            metadata[table.name] = SemanticAnalyzer._analyze_table(schema, table)

        SemanticAnalyzer._enrich_dependency_metadata(schema, metadata)

        return metadata

    @staticmethod
    def _analyze_table(schema: SchemaModel, table: TableModel) -> dict[str, Any]:
        classifications = {}
        computed_fields = []
        temporal_dependencies = []
        monetary_dependencies = []
        status_dependencies = []
        business_fields = []

        def is_fk(col_id: str) -> bool:
            for rel in schema.relationships:
                if rel.source_table_id == table.id and rel.source_column_id == col_id:
                    return True
                if rel.target_table_id == table.id and rel.target_column_id == col_id:
                    return True
            return False

        columns_by_name = {col.name.lower(): col.name for col in table.columns}
        col_names_lower = set(columns_by_name.keys())

        for col in table.columns:
            c_lower = col.name.lower()
            c_type = col.type.lower()

            classification = "Business Field"

            if col.is_primary_key:
                classification = "Primary Key"
            elif is_fk(col.id):
                classification = "Foreign Key"
            elif (
                c_type in ("date", "timestamp", "datetime")
                or c_lower.endswith("_at")
                or c_lower.endswith("_date")
            ):
                classification = "Temporal Field"
            elif (
                "total" in c_lower
                or "price" in c_lower
                or "amount" in c_lower
                or "salary" in c_lower
                or "tax" in c_lower
                or "discount" in c_lower
                or "shipping" in c_lower
                or "balance" in c_lower
            ):
                classification = "Monetary Field"
            elif (
                "percentage" in c_lower or "rate" in c_lower or c_lower.endswith("_pct")
            ):
                classification = "Percentage Field"
            elif "status" in c_lower or "state" in c_lower:
                classification = "Status Field"
            elif (
                c_lower.endswith("_id")
                or c_lower == "id"
                or c_lower == "uuid"
                or c_lower == "guid"
            ):
                classification = "Identifier"

            classifications[col.name] = classification

            if classification not in (
                "Primary Key",
                "Foreign Key",
                "Identifier",
                "Computed Field",
            ):
                business_fields.append(col.name)

            if c_lower in (
                "subtotal",
                "tax",
                "shipping",
                "discount",
                "total",
                "invoice_total",
                "balance",
                "remaining_balance",
                "grand_total",
            ):
                computed_fields.append(col.name)

        if "created_at" in col_names_lower and "updated_at" in col_names_lower:
            temporal_dependencies.append(
                [columns_by_name["created_at"], columns_by_name["updated_at"]]
            )

        if "order_date" in col_names_lower and "shipped_date" in col_names_lower:
            chain = [columns_by_name["order_date"], columns_by_name["shipped_date"]]
            if "delivery_date" in col_names_lower:
                chain.append(columns_by_name["delivery_date"])
            temporal_dependencies.append(chain)

        if "order_date" in col_names_lower and "ship_date" in col_names_lower:
            chain = [columns_by_name["order_date"], columns_by_name["ship_date"]]
            if "delivery_date" in col_names_lower:
                chain.append(columns_by_name["delivery_date"])
            temporal_dependencies.append(chain)

        if "birth_date" in col_names_lower and "hire_date" in col_names_lower:
            temporal_dependencies.append(
                [columns_by_name["birth_date"], columns_by_name["hire_date"]]
            )

        if "invoice_date" in col_names_lower and "due_date" in col_names_lower:
            temporal_dependencies.append(
                [columns_by_name["invoice_date"], columns_by_name["due_date"]]
            )

        if "visit_date" in col_names_lower and "discharge_date" in col_names_lower:
            temporal_dependencies.append(
                [columns_by_name["visit_date"], columns_by_name["discharge_date"]]
            )

        if "status" in col_names_lower and "completed_at" in col_names_lower:
            status_dependencies.append(
                [columns_by_name["status"], columns_by_name["completed_at"]]
            )

        if (
            "quantity" in col_names_lower
            and "unit_price" in col_names_lower
            and "subtotal" in col_names_lower
        ):
            monetary_dependencies.append(
                [
                    columns_by_name["quantity"],
                    columns_by_name["unit_price"],
                    columns_by_name["subtotal"],
                ]
            )

        if "salary" in col_names_lower and "currency" in col_names_lower:
            monetary_dependencies.append(
                [columns_by_name["salary"], columns_by_name["currency"]]
            )

        return {
            "classifications": classifications,
            "business_fields": business_fields,
            "computed_fields": computed_fields,
            "temporal_dependencies": temporal_dependencies,
            "monetary_dependencies": monetary_dependencies,
            "status_dependencies": status_dependencies,
        }

    @staticmethod
    def _enrich_dependency_metadata(
        schema: SchemaModel, metadata: dict[str, Any]
    ) -> None:
        table_map = {t.id: t for t in schema.tables}  # noqa: F841
        name_to_id = {t.name: t.id for t in schema.tables}  # noqa: F841
        id_to_name = {t.id: t.name for t in schema.tables}  # noqa: F841

        col_map: dict[str, dict[str, Any]] = {}
        for t in schema.tables:
            for c in t.columns:
                col_map[c.id] = {
                    "column": c,
                    "table_id": t.id,
                    "table_name": t.name,
                }

        for table in schema.tables:
            meta = metadata.setdefault(table.name, {})
            meta.setdefault("primary_keys", [])
            meta.setdefault("foreign_keys", [])
            meta.setdefault("depends_on", [])
            meta.setdefault("self_reference", False)
            meta.setdefault("self_reference_columns", [])
            meta.setdefault("junction_table", False)
            meta.setdefault("circular_depends_on", [])

        for table in schema.tables:
            meta = metadata[table.name]
            for col in table.columns:
                if col.is_primary_key and col.name not in meta["primary_keys"]:
                    meta["primary_keys"].append(col.name)

        fk_map: dict[str, list[dict[str, Any]]] = {}
        for table in schema.tables:
            fk_map[table.name] = []

        self_refs: dict[str, list[tuple[str, str]]] = {}
        circular_pairs: set[tuple[str, str]] = set()

        for rel in schema.relationships:
            src_col_info = col_map.get(rel.source_column_id)
            tgt_col_info = col_map.get(rel.target_column_id)

            if not src_col_info or not tgt_col_info:
                continue

            src_table = src_col_info["table_name"]
            tgt_table = tgt_col_info["table_name"]
            src_col_name = src_col_info["column"].name
            tgt_col_name = tgt_col_info["column"].name
            src_is_pk = src_col_info["column"].is_primary_key
            tgt_is_pk = tgt_col_info["column"].is_primary_key

            if src_table == tgt_table:
                self_refs.setdefault(src_table, [])
                if src_is_pk and not tgt_is_pk:
                    self_refs[src_table].append((tgt_col_name, src_col_name))
                elif tgt_is_pk and not src_is_pk:
                    self_refs[src_table].append((src_col_name, tgt_col_name))
                elif src_is_pk and tgt_is_pk:
                    self_refs[src_table].append((src_col_name, src_col_name))
                continue

            rel_type = rel.type.lower()

            _type_map = {
                "one-to-many": "1:n",
                "many-to-one": "n:1",
                "one-to-one": "1:1",
                "many-to-many": "m:n",
            }
            rel_type = _type_map.get(rel_type, rel_type)

            if rel_type == "m:n":
                continue

            if rel_type in ("1:n", "1:1"):
                parent_table = src_table
                parent_pk_col = src_col_name
                child_table = tgt_table
                child_fk_col = tgt_col_name
            elif rel_type == "n:1":
                parent_table = tgt_table
                parent_pk_col = tgt_col_name
                child_table = src_table
                child_fk_col = src_col_name
            elif src_is_pk and not tgt_is_pk:
                child_table = tgt_table
                parent_table = src_table
                child_fk_col = tgt_col_name
                parent_pk_col = src_col_name
            elif tgt_is_pk and not src_is_pk:
                child_table = src_table
                parent_table = tgt_table
                child_fk_col = src_col_name
                parent_pk_col = tgt_col_name
            else:
                continue

            fk_map[child_table].append(
                {
                    "fk_column": child_fk_col,
                    "pk_column": parent_pk_col,
                    "parent_table": parent_table,
                    "relationship_name": rel.name,
                }
            )

        for table in schema.tables:
            meta = metadata[table.name]
            for fk in fk_map[table.name]:
                parent = fk["parent_table"]
                if parent not in meta["depends_on"]:
                    meta["depends_on"].append(parent)
                if fk["fk_column"] not in meta["foreign_keys"]:
                    meta["foreign_keys"].append(fk["fk_column"])

        for table_name, refs in self_refs.items():
            meta = metadata[table_name]
            meta["self_reference"] = True
            for fk_col, pk_col in refs:
                if (fk_col, pk_col) not in meta["self_reference_columns"]:
                    meta["self_reference_columns"].append((fk_col, pk_col))

        depends_graph: dict[str, set[str]] = {}
        for table in schema.tables:
            depends_graph[table.name] = set(metadata[table.name]["depends_on"])

        for table_a in schema.tables:
            for table_b in schema.tables:
                if table_a.name >= table_b.name:
                    continue
                if table_a.name in depends_graph.get(
                    table_b.name, set()
                ) and table_b.name in depends_graph.get(table_a.name, set()):
                    circular_pairs.add((table_a.name, table_b.name))
                    if table_b.name not in metadata[table_a.name].get(
                        "circular_depends_on", []
                    ):
                        metadata[table_a.name].setdefault(
                            "circular_depends_on", []
                        ).append(table_b.name)
                    if table_a.name not in metadata[table_b.name].get(
                        "circular_depends_on", []
                    ):
                        metadata[table_b.name].setdefault(
                            "circular_depends_on", []
                        ).append(table_a.name)

        for table in schema.tables:
            meta = metadata[table.name]
            pk_cols = meta.get("primary_keys", [])
            if len(pk_cols) >= 2:
                pk_are_all_fk = True
                for col in table.columns:
                    if col.is_primary_key:
                        is_also_fk = False
                        for rel in schema.relationships:
                            if (
                                rel.source_table_id == table.id
                                and rel.source_column_id == col.id
                            ):
                                is_also_fk = True
                                break
                            if (
                                rel.target_table_id == table.id
                                and rel.target_column_id == col.id
                            ):
                                is_also_fk = True
                                break
                        if not is_also_fk:
                            pk_are_all_fk = False
                            break
                meta["junction_table"] = pk_are_all_fk

        for table in schema.tables:
            meta = metadata[table.name]
            for circ_dep in meta.get("circular_depends_on", []):
                if circ_dep in meta["depends_on"]:
                    meta["depends_on"].remove(circ_dep)

        for table in schema.tables:
            meta = metadata[table.name]
            if meta.get("self_reference", False):
                for sr_pk_col_name, _ in meta.get("self_reference_columns", []):
                    if sr_pk_col_name in meta.get("depends_on", []):
                        meta["depends_on"].remove(sr_pk_col_name)

        for table in schema.tables:
            meta = metadata[table.name]
            temp_depends = list(dict.fromkeys(meta.get("depends_on", [])))
            meta["depends_on"] = temp_depends

    @staticmethod
    def build_dependency_graph(
        metadata: dict[str, Any],
    ) -> DependencyGraph:
        """Build a DependencyGraph from analyzer metadata.

        Self-referencing and circular dependencies are excluded so that
        the topological sort contains only cycle-free edges.
        """
        graph = DependencyGraph()

        for table_name in metadata:
            graph.add_node(table_name)

        for table_name, meta in metadata.items():
            for dep in meta.get("depends_on", []):
                graph.add_edge(dep, table_name)

        return graph
