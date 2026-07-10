"""Math computer for deriving financial and statistical fields post-generation."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MathComputer:
    """Computes derived mathematical fields deterministically from raw business values."""

    @staticmethod
    def compute(
        _schema: Any,
        placeholders: dict[str, list[dict[str, Any]]],
    ) -> dict[str, int]:
        """In-place update of placeholder records with computed mathematical fields.

        Args:
            _schema: The schema containing table definitions.
            placeholders: Dictionary mapping table name to a list of records.

        Returns:
            dict[str, int]: Statistics about computations performed and skipped.
        """
        stats: dict[str, int] = {"computed": 0, "skipped_null_source": 0}
        for _table_name, records in placeholders.items():
            for record in records:
                from app.seeder.lineage import LineageEngine

                # Compute Subtotal
                if "subtotal" in record:
                    qty_raw = record.get("quantity")
                    price_raw = record.get("unit_price") or record.get("price")
                    if qty_raw is not None and price_raw is not None:
                        qty = float(str(qty_raw))
                        price = float(str(price_raw))
                        record["subtotal"] = round(qty * price, 2)
                        stats["computed"] += 1
                        LineageEngine.record_origin(
                            record,
                            "subtotal",
                            "Computed",
                            "Computed from quantity * unit_price.",
                        )
                    else:
                        logger.debug(
                            "MathComputer: skipping subtotal — quantity=%s, price=%s",
                            qty_raw,
                            price_raw,
                        )
                        stats["skipped_null_source"] += 1

                # Compute Tax
                if "tax" in record:
                    subtotal_raw = record.get("subtotal")
                    tax_rate_raw = record.get("tax_rate")
                    if subtotal_raw is not None and tax_rate_raw is not None:
                        subtotal = float(str(subtotal_raw))
                        tax_rate = float(str(tax_rate_raw))
                        record["tax"] = round(subtotal * tax_rate, 2)
                        stats["computed"] += 1
                        LineageEngine.record_origin(
                            record,
                            "tax",
                            "Computed",
                            "Computed from subtotal * tax_rate.",
                        )
                    else:
                        logger.debug(
                            "MathComputer: skipping tax — subtotal=%s, tax_rate=%s",
                            subtotal_raw,
                            tax_rate_raw,
                        )
                        stats["skipped_null_source"] += 1

                # Compute Grand Total / Invoice Total / Total
                total_fields = [
                    f for f in ["grand_total", "invoice_total", "total"] if f in record
                ]
                if total_fields:
                    subtotal_raw = record.get("subtotal")
                    discount_raw = record.get("discount")
                    tax_raw = record.get("tax")
                    shipping_raw = record.get("shipping")

                    # subtotal is required; others default to 0.0 if missing but warn if explicitly None
                    if subtotal_raw is not None:
                        subtotal = float(str(subtotal_raw))
                        discount = (
                            0.0 if discount_raw is None else float(str(discount_raw))
                        )
                        tax = 0.0 if tax_raw is None else float(str(tax_raw))
                        shipping = (
                            0.0 if shipping_raw is None else float(str(shipping_raw))
                        )
                        total_val = round(subtotal - discount + tax + shipping, 2)

                        for tf in total_fields:
                            record[tf] = total_val
                            stats["computed"] += 1
                            LineageEngine.record_origin(
                                record,
                                tf,
                                "Computed",
                                "Computed from subtotal - discount + tax + shipping.",
                            )

                        if discount_raw is None and "discount" in record:
                            logger.debug(
                                "MathComputer: discount is None for total, using 0.0"
                            )
                        if tax_raw is None and "tax" in record:
                            logger.debug(
                                "MathComputer: tax is None for total, using 0.0"
                            )
                        if shipping_raw is None and "shipping" in record:
                            logger.debug(
                                "MathComputer: shipping is None for total, using 0.0"
                            )
                    else:
                        logger.debug(
                            "MathComputer: skipping total — subtotal is None",
                        )
                        stats["skipped_null_source"] += 1

                # Compute Remaining Balance
                if "remaining_balance" in record:
                    total_raw = (
                        record.get("grand_total")
                        or record.get("invoice_total")
                        or record.get("total")
                    )
                    amount_raw = record.get("amount_paid") or record.get("paid_amount")
                    if total_raw is not None and amount_raw is not None:
                        total_val = float(str(total_raw))
                        amount_paid = float(str(amount_raw))
                        record["remaining_balance"] = round(total_val - amount_paid, 2)
                        stats["computed"] += 1
                        LineageEngine.record_origin(
                            record,
                            "remaining_balance",
                            "Computed",
                            "Computed from total - amount_paid.",
                        )
                    else:
                        logger.debug(
                            "MathComputer: skipping remaining_balance — total=%s, amount_paid=%s",
                            total_raw,
                            amount_raw,
                        )
                        stats["skipped_null_source"] += 1

        return stats
