"""Explainability and Data Lineage Engine."""

from typing import Any

from app.schemas.schema_design import SchemaModel


class LineageEngine:
    """Records how every generated value was produced to provide explainability."""

    @staticmethod
    def init_lineage(record: dict[str, Any]) -> None:
        if "_lineage" not in record:
            record["_lineage"] = {}

    @staticmethod
    def record_origin(
        record: dict[str, Any], column: str, origin: str, reason: str
    ) -> None:
        LineageEngine.init_lineage(record)

        if column not in record["_lineage"]:
            record["_lineage"][column] = {
                "origin": origin,
                "reason": reason,
                "history": [],
            }
        else:
            # Move current to history and update
            record["_lineage"][column]["history"].append(
                {
                    "origin": record["_lineage"][column]["origin"],
                    "reason": record["_lineage"][column]["reason"],
                }
            )
            record["_lineage"][column]["origin"] = origin
            record["_lineage"][column]["reason"] = reason

    @staticmethod
    def get_lineage_graph(schema: SchemaModel) -> str:
        """Returns a string representation of the table dependency graph."""
        graph = ""
        # Create a simple topological representation
        visited = set()

        def traverse(table_id: str, indent: str = "") -> None:
            nonlocal graph
            if table_id in visited:
                return
            visited.add(table_id)

            t = next((t for t in schema.tables if t.id == table_id), None)
            if t:
                graph += f"{indent}{t.name}\n"
                # Find children
                children = [
                    r.source_table_id
                    for r in schema.relationships
                    if r.target_table_id == table_id
                ]
                for child in children:
                    traverse(child, indent + "    ")

        # Find root tables
        targets = {r.source_table_id for r in schema.relationships}
        roots = [t.id for t in schema.tables if t.id not in targets]
        if not roots:
            roots = [t.id for t in schema.tables]

        for root in roots:
            traverse(root)

        return graph.strip()
