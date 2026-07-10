"""Unit tests for extended SeederValidator methods (referential integrity, etc.)."""

from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)
from app.seeder.validator import SeederValidator


class TestReferentialIntegrity:
    def test_valid_fk_references(self):
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
                ),
            ],
        )

        placeholders = {
            "Customers": [{"_ref_id": "c1", "id": 1}, {"_ref_id": "c2", "id": 2}],
            "Orders": [
                {"_ref_id": "o1", "order_id": 101, "customer_id": 1},
                {"_ref_id": "o2", "order_id": 102, "customer_id": 2},
            ],
        }

        errors = SeederValidator.validate_referential_integrity(schema, placeholders)
        assert errors == []

    def test_missing_fk_reference(self):
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
                ),
            ],
        )

        placeholders = {
            "Customers": [{"_ref_id": "c1", "id": 1}],
            "Orders": [
                {"_ref_id": "o1", "order_id": 101, "customer_id": 1},
                {"_ref_id": "o2", "order_id": 102, "customer_id": 99},
            ],
        }

        errors = SeederValidator.validate_referential_integrity(schema, placeholders)
        assert len(errors) == 1
        assert "99" in errors[0]
        assert "customer_id" in errors[0]

    def test_null_fk_no_error(self):
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
                            isNullable=True,
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
                    isRequired=False,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )

        placeholders = {
            "Customers": [{"_ref_id": "c1", "id": 1}],
            "Orders": [
                {"_ref_id": "o1", "order_id": 101, "customer_id": None},
            ],
        }

        errors = SeederValidator.validate_referential_integrity(schema, placeholders)
        assert errors == []


class TestPKUniqueness:
    def _schema(self, pk_cols: list[str]) -> SchemaModel:
        cols = list(dict.fromkeys(pk_cols))
        return SchemaModel(
            tables=[
                TableModel(
                    id="t1",
                    name="Customers",
                    columns=[
                        ColumnModel(
                            id=f"c{i}",
                            name=col,
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        )
                        for i, col in enumerate(cols)
                    ],
                ),
            ],
            relationships=[],
        )

    def test_unique_pks(self):
        schema = self._schema(["id"])
        placeholders = {
            "Customers": [
                {"_ref_id": "c1", "id": 1},
                {"_ref_id": "c2", "id": 2},
            ],
        }
        errors = SeederValidator.validate_pk_uniqueness(schema, placeholders)
        assert errors == []

    def test_duplicate_pks(self):
        schema = self._schema(["id"])
        placeholders = {
            "Customers": [
                {"_ref_id": "c1", "id": 1},
                {"_ref_id": "c2", "id": 1},
            ],
        }
        errors = SeederValidator.validate_pk_uniqueness(schema, placeholders)
        assert len(errors) >= 1
        assert "duplicated" in errors[0]


class TestSelfReferences:
    def test_no_self_ref_violation(self):
        placeholders = {
            "Employees": [
                {"_ref_id": "e1", "emp_id": 1, "manager_id": None},
                {"_ref_id": "e2", "emp_id": 2, "manager_id": 1},
            ],
        }
        errors = SeederValidator.validate_self_references(placeholders)
        assert errors == []

    def test_self_ref_violation(self):
        placeholders = {
            "Employees": [
                {"_ref_id": "e1", "emp_id": 1, "manager_id": 1},
            ],
        }
        errors = SeederValidator.validate_self_references(placeholders)
        assert len(errors) >= 1
        assert "manager_id" in errors[0]


class TestJunctionUniqueness:
    def test_unique_junction_pairs(self):
        placeholders = {
            "Enrollments": [
                {"_ref_id": "e1", "student_id": 1, "course_id": 10},
                {"_ref_id": "e2", "student_id": 1, "course_id": 20},
                {"_ref_id": "e3", "student_id": 2, "course_id": 10},
            ],
        }
        errors = SeederValidator.validate_junction_uniqueness(placeholders)
        assert errors == []

    def test_duplicate_junction_pairs(self):
        placeholders = {
            "Enrollments": [
                {"_ref_id": "e1", "student_id": 1, "course_id": 10},
                {"_ref_id": "e2", "student_id": 1, "course_id": 10},
            ],
        }
        errors = SeederValidator.validate_junction_uniqueness(placeholders)
        assert len(errors) >= 1
        assert "duplicate" in errors[0].lower()
