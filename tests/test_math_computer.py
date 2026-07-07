"""Unit tests for MathComputer."""

from app.schemas.schema_design import SchemaModel
from app.seeder.math_computer import MathComputer


def test_math_computer_derived_fields():
    """Test that math computer derives financial fields correctly."""
    schema = SchemaModel(tables=[], relationships=[])

    placeholders = {
        "Invoices": [
            {
                "quantity": 5,
                "unit_price": 20.0,
                "tax_rate": 0.05,
                "discount": 10.0,
                "shipping": 15.0,
                "amount_paid": 50.0,
                "subtotal": None,
                "tax": None,
                "grand_total": None,
                "remaining_balance": None,
            },
            {
                "quantity": 2,
                "price": 50.0,
                "tax_rate": 0.10,
                "discount": 0.0,
                "shipping": 0.0,
                "paid_amount": 100.0,
                "subtotal": None,
                "tax": None,
                "invoice_total": None,
                "remaining_balance": None,
            },
        ]
    }

    MathComputer.compute(schema, placeholders)

    # Invoice 1
    inv1 = placeholders["Invoices"][0]
    assert inv1["subtotal"] == 100.0  # 5 * 20
    assert inv1["tax"] == 5.0  # 100 * 0.05
    assert inv1["grand_total"] == 110.0  # 100 - 10 + 5 + 15
    assert inv1["remaining_balance"] == 60.0  # 110 - 50

    # Invoice 2
    inv2 = placeholders["Invoices"][1]
    assert inv2["subtotal"] == 100.0  # 2 * 50
    assert inv2["tax"] == 10.0  # 100 * 0.10
    assert inv2["invoice_total"] == 110.0  # 100 - 0 + 10 + 0
    assert inv2["remaining_balance"] == 10.0  # 110 - 100
