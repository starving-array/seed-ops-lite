"""Unit tests for the RecordAllocator."""

from app.schemas.schema_design import ColumnModel, SchemaModel, TableModel
from app.seeder.allocator import RecordAllocator


def test_allocate_placeholders():
    """Test that placeholders are correctly allocated based on targets and schema."""
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
                    ),
                    ColumnModel(
                        id="c2",
                        name="name",
                        type="string",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
            TableModel(
                id="t2",
                name="Orders",
                columns=[
                    ColumnModel(
                        id="c3",
                        name="order_id",
                        type="integer",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    ),
                    ColumnModel(
                        id="c4",
                        name="customer_id",
                        type="integer",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
        ],
        relationships=[],
    )

    ordered_tables = ["Customers", "Orders"]
    row_targets = {"Customers": 2, "Orders": 3}

    allocated = RecordAllocator.allocate(schema, ordered_tables, row_targets)

    # Verify Customers
    assert "Customers" in allocated
    assert len(allocated["Customers"]) == 2
    for i, record in enumerate(allocated["Customers"]):
        assert "_ref_id" in record
        assert isinstance(record["_ref_id"], str)
        assert record["_table"] == "Customers"
        assert record["_index"] == i
        assert "id" in record
        assert "name" in record
        assert record["id"] is None
        assert record["name"] is None

    # Verify Orders
    assert "Orders" in allocated
    assert len(allocated["Orders"]) == 3
    for i, record in enumerate(allocated["Orders"]):
        assert "_ref_id" in record
        assert isinstance(record["_ref_id"], str)
        assert record["_table"] == "Orders"
        assert record["_index"] == i
        assert "order_id" in record
        assert "customer_id" in record
        assert record["order_id"] is None
        assert record["customer_id"] is None
