"""Unit tests for the RelationshipAllocator."""

from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)
from app.seeder.relationship_allocator import RelationshipAllocator


def test_allocate_relationships():
    """Test mapping generation across different cardinalities."""
    schema = SchemaModel(
        tables=[
            TableModel(
                id="tbl1",
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
                id="tbl2",
                name="Orders",
                columns=[
                    ColumnModel(
                        id="c2",
                        name="id",
                        type="integer",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            ),
        ],
        relationships=[
            RelationshipModel(
                id="rel1",
                name="Customer_Orders",
                sourceTableId="tbl1",
                sourceColumnId="c1",
                targetTableId="tbl2",
                targetColumnId="c2",
                type="1:n",
                isRequired=True,
                cascadeDelete=False,
                cascadeUpdate=False,
            ),
            RelationshipModel(
                id="rel2",
                name="Order_Customer",
                sourceTableId="tbl2",
                sourceColumnId="c2",
                targetTableId="tbl1",
                targetColumnId="c1",
                type="n:1",
                isRequired=True,
                cascadeDelete=False,
                cascadeUpdate=False,
            ),
            RelationshipModel(
                id="rel3",
                name="Customer_Order_11",
                sourceTableId="tbl1",
                sourceColumnId="c1",
                targetTableId="tbl2",
                targetColumnId="c2",
                type="1:1",
                isRequired=False,
                cascadeDelete=False,
                cascadeUpdate=False,
            ),
            RelationshipModel(
                id="rel4",
                name="Customer_Order_MN",
                sourceTableId="tbl1",
                sourceColumnId="c1",
                targetTableId="tbl2",
                targetColumnId="c2",
                type="m:n",
                isRequired=False,
                cascadeDelete=False,
                cascadeUpdate=False,
            ),
        ],
    )

    placeholders = {
        "Customers": [
            {"_ref_id": "cust1", "_table": "Customers", "_index": 0},
            {"_ref_id": "cust2", "_table": "Customers", "_index": 1},
        ],
        "Orders": [
            {"_ref_id": "ord1", "_table": "Orders", "_index": 0},
            {"_ref_id": "ord2", "_table": "Orders", "_index": 1},
            {"_ref_id": "ord3", "_table": "Orders", "_index": 2},
        ],
    }

    rel_map = RelationshipAllocator.allocate(schema, placeholders, seed=42)

    # Verify 1:N
    assert "Customer_Orders" in rel_map
    map_1n = rel_map["Customer_Orders"]
    targets = []
    for src, tgts in map_1n.items():
        assert src in ["cust1", "cust2"]
        targets.extend(tgts)
    assert len(targets) == 3
    assert set(targets) == {"ord1", "ord2", "ord3"}

    # Verify N:1
    assert "Order_Customer" in rel_map
    map_n1 = rel_map["Order_Customer"]
    sources = []
    for src, tgts in map_n1.items():
        assert src in ["ord1", "ord2", "ord3"]
        sources.append(src)
        assert len(tgts) == 1
        assert tgts[0] in ["cust1", "cust2"]
    assert len(sources) == 3

    # Verify 1:1
    assert "Customer_Order_11" in rel_map
    map_11 = rel_map["Customer_Order_11"]
    total_mapped = 0
    for _, tgts in map_11.items():
        assert len(tgts) == 1
        total_mapped += 1
    assert total_mapped == 2  # min(2, 3)

    # Verify M:N
    assert "Customer_Order_MN" in rel_map
    map_mn = rel_map["Customer_Order_MN"]
    assert len(map_mn) > 0
