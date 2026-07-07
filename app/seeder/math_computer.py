"""Math computer for deriving financial and statistical fields post-generation."""

from typing import Any


class MathComputer:
    """Computes derived mathematical fields deterministically from raw business values."""

    @staticmethod
    def compute(
        _schema: Any,
        placeholders: dict[str, list[dict[str, Any]]],
    ) -> None:
        """In-place update of placeholder records with computed mathematical fields.

        Args:
            schema: The schema containing table definitions.
            placeholders: Dictionary mapping table name to a list of records.
        """
        for _table_name, records in placeholders.items():
            for record in records:
                # Extract potential raw business values (defaulting to safe values if missing)
                qty = float(record.get("quantity") if record.get("quantity") is not None else 1.0)  # type: ignore
                price = float(record.get("unit_price") if record.get("unit_price") is not None else (record.get("price") or 0.0))  # type: ignore
                tax_rate = float(record.get("tax_rate") if record.get("tax_rate") is not None else 0.10)  # type: ignore
                discount = float(record.get("discount") if record.get("discount") is not None else 0.0)  # type: ignore
                shipping = float(record.get("shipping") if record.get("shipping") is not None else 0.0)  # type: ignore
                amount_paid = float(record.get("amount_paid") if record.get("amount_paid") is not None else (record.get("paid_amount") or 0.0))  # type: ignore

                # Compute Subtotal
                if "subtotal" in record:
                    record["subtotal"] = round(qty * price, 2)

                subtotal = float(record.get("subtotal") if record.get("subtotal") is not None else (qty * price))  # type: ignore

                # Compute Tax
                if "tax" in record:
                    record["tax"] = round(subtotal * tax_rate, 2)

                tax = float(record.get("tax") if record.get("tax") is not None else (subtotal * tax_rate))  # type: ignore

                # Compute Grand Total / Invoice Total
                total = round(subtotal - discount + tax + shipping, 2)

                if "grand_total" in record:
                    record["grand_total"] = total

                if "invoice_total" in record:
                    record["invoice_total"] = total

                if "total" in record:
                    record["total"] = total

                # Compute Remaining Balance
                if "remaining_balance" in record:
                    record["remaining_balance"] = round(total - amount_paid, 2)
