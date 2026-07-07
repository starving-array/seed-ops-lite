"""Unit tests for the ForeignKeyInjector."""

from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)
from app.seeder.fk_injector import ForeignKeyInjector


def test_fk_injection():
    """Test that foreign keys are properly injected into child records."""
    schema = SchemaModel(
        tables=[
            TableModel(
                id="t1",
                name="Customers",
                columns=[
                    ColumnModel(
                        id="c1",
                        name="id",
                        type="integer",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            ),
            TableModel(
                id="t2",
                name="Orders",
                columns=[
                    ColumnModel(
                        id="c2",
                        name="order_id",
                        type="integer",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    ),
                    ColumnModel(
                        id="c3",
                        name="customer_id",
                        type="integer",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
        ],
        relationships=[
            RelationshipModel(
                id="rel1",
                name="Customer_Orders",
                sourceTableId="t1",
                sourceColumnId="c1",
                targetTableId="t2",
                targetColumnId="c3",
                type="1:n",
                isRequired=True,
                cascadeDelete=False,
                cascadeUpdate=False,
            )
        ],
    )

    placeholders = {
        "Customers": [
            {"_ref_id": "cust1", "id": 100},
            {"_ref_id": "cust2", "id": 101},
        ],
        "Orders": [
            {"_ref_id": "ord1", "order_id": 500, "customer_id": None},
            {"_ref_id": "ord2", "order_id": 501, "customer_id": None},
            {"_ref_id": "ord3", "order_id": 502, "customer_id": None},
        ],
    }

    relationship_map = {
        "Customer_Orders": {
            "cust1": ["ord1", "ord3"],
            "cust2": ["ord2"],
        }
    }

    stats = ForeignKeyInjector.inject(schema, placeholders, relationship_map)

    assert stats.total_injected == 3
    assert stats.by_relationship["Customer_Orders"] == 3

    # Check that ord1 and ord3 got cust1's ID (100)
    assert placeholders["Orders"][0]["customer_id"] == 100
    assert placeholders["Orders"][2]["customer_id"] == 100

    # Check that ord2 got cust2's ID (101)
    assert placeholders["Orders"][1]["customer_id"] == 101

    # Ensure no orphans
    for order in placeholders["Orders"]:
        assert order["customer_id"] is not None
