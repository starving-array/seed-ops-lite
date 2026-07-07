"""Semantic Dependency Analyzer for Database Schemas."""

from typing import Any

from app.schemas.schema_design import SchemaModel, TableModel


class SemanticAnalyzer:
    """Analyzes table columns to discover semantic classifications and dependencies."""

    @staticmethod
    def analyze(schema: SchemaModel) -> dict[str, Any]:
        """Produce semantic metadata for all tables in the schema."""
        metadata = {}
        for table in schema.tables:
            metadata[table.name] = SemanticAnalyzer._analyze_table(schema, table)
        return metadata

    @staticmethod
    def _analyze_table(schema: SchemaModel, table: TableModel) -> dict[str, Any]:
        classifications = {}
        computed_fields = []
        temporal_dependencies = []
        monetary_dependencies = []
        status_dependencies = []
        business_fields = []

        # Helper to determine if column is FK
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

            # Classification
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

            # Math / Computed
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

        # Temporal Dependencies (chains)
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

        # Status Dependencies
        if "status" in col_names_lower and "completed_at" in col_names_lower:
            status_dependencies.append(
                [columns_by_name["status"], columns_by_name["completed_at"]]
            )

        # Monetary Dependencies
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
