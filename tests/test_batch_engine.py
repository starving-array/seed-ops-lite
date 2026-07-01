import pytest

from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)
from app.seeder.batch_engine import calculate_batch_size


def test_calculate_batch_size_empty():
    schema = SchemaModel(tables=[], relationships=[])
    assert calculate_batch_size(schema, {}) == 10


def test_calculate_batch_size_small_dataset():
    schema = SchemaModel(
        tables=[
            TableModel(
                id="1",
                name="users",
                columns=[
                    ColumnModel(
                        id="c1",
                        name="id",
                        type="INTEGER",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            )
        ],
        relationships=[],
    )
    # Total rows <= 100
    batch_size = calculate_batch_size(schema, {"users": 50})
    assert (
        batch_size == 15
    )  # Base batch is 10 for <=100 rows, simple multiplier 1.5, final_batch max of 5, min(15, 50) -> 15.


def test_calculate_batch_size_large_dataset():
    schema = SchemaModel(
        tables=[
            TableModel(
                id="1",
                name="users",
                columns=[
                    ColumnModel(
                        id="c1",
                        name="id",
                        type="INTEGER",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            )
        ],
        relationships=[],
    )
    # Total rows = 5000 -> base_batch = 250.
    # Simple schema multiplier is 1.5 -> 250 * 1.5 = 375.
    batch_size = calculate_batch_size(schema, {"users": 5000})
    assert batch_size == 375


def test_calculate_batch_size_complex_schema():
    # Many tables, relationships, and columns
    tables = []
    relationships = []
    row_targets = {}
    for i in range(1, 12):
        tables.append(
            TableModel(
                id=str(i),
                name=f"table_{i}",
                columns=[
                    ColumnModel(
                        id=f"c_{i}_{j}",
                        name=f"col_{j}",
                        type="VARCHAR",
                        isPrimaryKey=(j == 1),
                        isNullable=False,
                        defaultValue="",
                    )
                    for j in range(1, 15)  # 14 columns
                ],
            )
        )
        row_targets[f"table_{i}"] = 200  # Total = 2200 -> base_batch = 250

    for i in range(2, 12):
        relationships.append(
            RelationshipModel(
                id=f"r_{i}",
                name=f"fk_table_{i}_table_1",
                sourceTableId=str(i),
                sourceColumnId=f"c_{i}_2",
                targetTableId="1",
                targetColumnId="c_1_1",
                type="many-to-one",
                isRequired=True,
                cascadeDelete=True,
                cascadeUpdate=True,
            )
        )

    schema = SchemaModel(tables=tables, relationships=relationships)
    # Total rows = 2200 -> base_batch = 250.
    # Complex schema (num_tables=11 > 8, relationships=10) -> multiplier = 0.7.
    # 250 * 0.7 = 175
    batch_size = calculate_batch_size(schema, row_targets)
    assert batch_size == 175


def test_calculate_batch_size_configuration_driven():
    from app.core.settings.config import settings

    schema = SchemaModel(
        tables=[
            TableModel(
                id="1",
                name="users",
                columns=[
                    ColumnModel(
                        id="c1",
                        name="id",
                        type="INTEGER",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            )
        ],
        relationships=[],
    )

    # Let's temporarily override the settings thresholds and batch sizes
    original_threshold = settings.BATCH_THRESHOLD_SMALL
    original_size = settings.BATCH_SIZE_SMALL
    try:
        settings.BATCH_THRESHOLD_SMALL = 500
        settings.BATCH_SIZE_SMALL = 99
        # Total rows = 200 <= 500 (which is now BATCH_THRESHOLD_SMALL)
        # Base batch size should be 99. Simple schema multiplier 1.5 -> 99 * 1.5 = 148.5 -> 148.
        batch_size = calculate_batch_size(schema, {"users": 200})
        assert batch_size == 148
    finally:
        settings.BATCH_THRESHOLD_SMALL = original_threshold
        settings.BATCH_SIZE_SMALL = original_size


@pytest.mark.asyncio
async def test_email_branding_generation():
    from app.core.settings.config import settings
    from app.seeder.models import FieldDefinition, SeedRequest
    from app.seeder.seeder import HybridSeeder

    original_domain = settings.DEFAULT_EMAIL_DOMAIN
    try:
        settings.DEFAULT_EMAIL_DOMAIN = "brandedops.com"
        seeder = HybridSeeder()
        # Seed request for a simple table with email field
        req = SeedRequest(
            target="users",
            num_records=2,
            fields={
                "email": FieldDefinition(
                    type="email",
                    rules={"default": "test.user@some-other-domain.com"},
                )
            },
            seed=42,
            strict=True,
        )
        res = await seeder.seed(req)
        assert res.success
        assert len(res.records) == 2
        # Verify branding applied
        assert res.records[0].data["email"] == "test.user@brandedops.com"
        assert res.records[1].data["email"] == "test.user@brandedops.com"
    finally:
        settings.DEFAULT_EMAIL_DOMAIN = original_domain
