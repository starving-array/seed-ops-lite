"""Generic Business Rule Engine for synthetic data."""

from datetime import datetime, timedelta
from typing import Any

from app.schemas.schema_design import SchemaModel


class BusinessRuleEngine:
    """Enforces and repairs business rules based on semantic dependencies."""

    @staticmethod
    def enforce(
        _schema: SchemaModel,
        placeholders: dict[str, list[dict[str, Any]]],
        semantic_metadata_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply rules to records and repair violations."""
        stats: dict[str, Any] = {
            "rules_evaluated": 0,
            "rules_violated": 0,
            "rules_repaired": 0,
            "repairs": [],
        }

        from app.seeder.lineage import LineageEngine

        for table_name, records in placeholders.items():
            metadata = semantic_metadata_map.get(table_name, {})
            temporal_deps = metadata.get("temporal_dependencies", [])
            status_deps = metadata.get("status_dependencies", [])
            classifications = metadata.get("classifications", {})

            for rec in records:
                # 1. Temporal Rules
                for chain in temporal_deps:
                    for i in range(len(chain) - 1):
                        col1, col2 = chain[i], chain[i + 1]
                        val1, val2 = rec.get(col1), rec.get(col2)

                        stats["rules_evaluated"] += 1
                        if val1 and val2:
                            try:
                                d1 = datetime.fromisoformat(val1)
                                d2 = datetime.fromisoformat(val2)
                                if d1 > d2:
                                    stats["rules_violated"] += 1
                                    # Repair: shift col2 forward
                                    delta = (d1 - d2).days + 1
                                    if delta < 1:
                                        delta = 1
                                    new_d2 = d1 + timedelta(days=delta)
                                    # Handle string length difference (e.g. if 'Z' is used)
                                    rec[col2] = new_d2.isoformat()
                                    stats["rules_repaired"] += 1
                                    reason = f"{table_name}: Shifted {col2} forward to be after {col1}"
                                    stats["repairs"].append(reason)
                                    LineageEngine.record_origin(
                                        rec, col2, "Business Rule Corrected", reason
                                    )
                            except Exception as e:
                                import logging

                                logging.debug(f"Date parsing failed: {e}")

                # 2. Numeric Range & Monetary Rules
                for col_name, val in list(rec.items()):
                    if val is None or not isinstance(val, int | float):
                        continue

                    cls = classifications.get(col_name, "")

                    if cls == "Monetary Field":
                        stats["rules_evaluated"] += 1
                        if val < 0:
                            stats["rules_violated"] += 1
                            rec[col_name] = abs(val)
                            stats["rules_repaired"] += 1
                            reason = f"{table_name}: Fixed negative {col_name}"
                            stats["repairs"].append(reason)
                            LineageEngine.record_origin(
                                rec, col_name, "Business Rule Corrected", reason
                            )

                        # Basic salary check
                        if "salary" in col_name.lower():
                            stats["rules_evaluated"] += 1
                            if val < 1000:
                                stats["rules_violated"] += 1
                                rec[col_name] = val * 1000 if val > 0 else 50000.0
                                stats["rules_repaired"] += 1
                                reason = f"{table_name}: Adjusted unrealistic salary"
                                stats["repairs"].append(reason)
                                LineageEngine.record_origin(
                                    rec, col_name, "Business Rule Corrected", reason
                                )

                    if cls == "Percentage Field":
                        stats["rules_evaluated"] += 1
                        if val < 0 or val > 100:
                            stats["rules_violated"] += 1
                            rec[col_name] = max(0, min(100, val))
                            stats["rules_repaired"] += 1
                            reason = f"{table_name}: Clamped {col_name} to 0-100"
                            stats["repairs"].append(reason)
                            LineageEngine.record_origin(
                                rec, col_name, "Business Rule Corrected", reason
                            )

                    if "quantity" in col_name.lower():
                        stats["rules_evaluated"] += 1
                        if val < 1:
                            stats["rules_violated"] += 1
                            rec[col_name] = 1
                            stats["rules_repaired"] += 1
                            reason = f"{table_name}: Fixed {col_name} < 1"
                            stats["repairs"].append(reason)
                            LineageEngine.record_origin(
                                rec, col_name, "Business Rule Corrected", reason
                            )

                # 3. Status Rules
                for chain in status_deps:
                    if len(chain) == 2:
                        status_col, date_col = chain
                        status_val = str(rec.get(status_col, "")).lower()

                        stats["rules_evaluated"] += 1
                        if "pending" in status_val:
                            if rec.get(date_col) is not None:
                                stats["rules_violated"] += 1
                                rec[date_col] = None
                                stats["rules_repaired"] += 1
                                reason = f"{table_name}: Cleared {date_col} because status is {status_val}"
                                stats["repairs"].append(reason)
                                LineageEngine.record_origin(
                                    rec, date_col, "Business Rule Corrected", reason
                                )
                        elif (
                            "completed" in status_val or "success" in status_val
                        ) and not rec.get(date_col):
                            stats["rules_violated"] += 1
                            rec[date_col] = datetime.now().isoformat()
                            stats["rules_repaired"] += 1
                            reason = f"{table_name}: Set {date_col} because status is {status_val}"
                            stats["repairs"].append(reason)
                            LineageEngine.record_origin(
                                rec, date_col, "Business Rule Corrected", reason
                            )

        return stats
