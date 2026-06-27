"""Tests for the Relationship Binding Engine."""

import pytest

from app.binding.binder import BindingEngine
from app.binding.models import BindingRequest, RelationshipReference, RelationshipType
from app.workers.models import ExecutionUnit

# A valid SQL DDL schema for testing relationships
TEST_SCHEMA_DDL = """
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

CREATE TABLE posts (
    id INT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(100) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE profiles (
    id INT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    bio TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


@pytest.mark.asyncio
async def test_many_to_one_binding() -> None:
    """Test standard many-to-one parent-child binding and round-robin assignment."""
    engine = BindingEngine()

    records = {
        "users": [
            {"id": 101, "name": "Alice"},
            {"id": 102, "name": "Bob"},
        ],
        "posts": [
            {"id": 1, "user_id": None, "title": "Post A"},
            {"id": 2, "user_id": None, "title": "Post B"},
            {"id": 3, "user_id": None, "title": "Post C"},
        ],
    }

    request = BindingRequest(records=records, schema_ddl=TEST_SCHEMA_DDL)
    result = await engine.bind(request)

    assert result.success
    assert len(result.errors) == 0

    posts = result.records["posts"]
    assert len(posts) == 3

    # Round robin: posts[0]->101, posts[1]->102, posts[2]->101
    assert posts[0].data["user_id"] == 101
    assert posts[1].data["user_id"] == 102
    assert posts[2].data["user_id"] == 101

    assert result.statistics.total_records == 5
    assert result.statistics.bound_records == 3
    assert result.statistics.unresolved_references_count == 0


@pytest.mark.asyncio
async def test_one_to_one_binding() -> None:
    """Test unique mapping constraints for one-to-one relationships."""
    engine = BindingEngine()

    records = {
        "users": [
            {"id": 101, "name": "Alice"},
            {"id": 102, "name": "Bob"},
        ],
        "profiles": [
            {"id": 1, "user_id": None, "bio": "Bio A"},
            {"id": 2, "user_id": None, "bio": "Bio B"},
        ],
    }

    request = BindingRequest(records=records, schema_ddl=TEST_SCHEMA_DDL)
    result = await engine.bind(request)

    assert result.success

    profiles = result.records["profiles"]
    user_id_1 = profiles[0].data["user_id"]
    user_id_2 = profiles[1].data["user_id"]

    assert user_id_1 in [101, 102]
    assert user_id_2 in [101, 102]
    assert user_id_1 != user_id_2  # Strictly unique one-to-one mapping


@pytest.mark.asyncio
async def test_one_to_one_unresolved_overflow() -> None:
    """Test that one-to-one triggers unresolved flags if parents are exhausted."""
    engine = BindingEngine()

    records = {
        "users": [
            {"id": 101, "name": "Alice"},
        ],
        "profiles": [
            {"id": 1, "user_id": None, "bio": "Bio A"},
            {"id": 2, "user_id": None, "bio": "Bio B"},  # Exceeds count of users
        ],
    }

    request = BindingRequest(records=records, schema_ddl=TEST_SCHEMA_DDL)
    result = await engine.bind(request)

    # Required column user_id will fail because user_id 2 cannot be resolved
    assert not result.success
    assert len(result.errors) > 0
    assert result.statistics.unresolved_references_count == 1
    assert result.statistics.integrity_violations_count == 1


@pytest.mark.asyncio
async def test_referential_integrity_violation_orphans() -> None:
    """Test that validation detects foreign key values pointing to missing parent keys."""
    from app.binding.resolver import RelationshipResolver
    from app.binding.validator import ReferentialValidator

    records = {
        "users": [
            {"id": 101, "name": "Alice"},
        ],
        "posts": [
            # Manual orphan key insertion
            {"id": 1, "user_id": 999, "title": "Orphan Post"},
        ],
    }

    resolver = RelationshipResolver()
    _, relationships = resolver.get_relationship_references(
        TEST_SCHEMA_DDL,
        {
            "posts": [
                RelationshipReference(
                    local_column="user_id",
                    referenced_table="users",
                    referenced_column="id",
                    relationship_type=RelationshipType.MANY_TO_ONE,
                )
            ]
        },
    )

    validator = ReferentialValidator()
    errors = validator.validate(records, TEST_SCHEMA_DDL, relationships)

    assert len(errors) == 1
    assert any("has orphan value '999'" in err for err in errors)


@pytest.mark.asyncio
async def test_required_constraint_violation() -> None:
    """Test that missing required columns trigger validation errors."""
    engine = BindingEngine()

    records = {
        "users": [],  # No parents generated at all
        "posts": [
            {"id": 1, "user_id": None, "title": "Post A"},
        ],
    }

    request = BindingRequest(records=records, schema_ddl=TEST_SCHEMA_DDL)
    result = await engine.bind(request)

    assert not result.success
    assert any("is null or missing" in err for err in result.errors)


@pytest.mark.asyncio
async def test_ddl_resolution_failure() -> None:
    """Test that invalid DDL structures raise a DependencyResolutionException."""
    engine = BindingEngine()
    request = BindingRequest(
        records={},
        schema_ddl="CREATE TABLE INVALID",  # Missing parenthesis/fields
    )

    # In binders, errors during DDL parsing map to result.success = False or raise inside resolver
    # Let's verify that resolving with invalid DDL returns success = False and error message
    result = await engine.bind(request)
    assert not result.success
    assert any("No tables found" in err for err in result.errors)


@pytest.mark.asyncio
async def test_worker_framework_integration() -> None:
    """Test that execute_unit cleanly maps ExecutionUnit payloads to Binder runs."""
    engine = BindingEngine()

    unit = ExecutionUnit(
        unit_id="unit-binding-456",
        task_type="binding",
        target="db_binding",
        payload={
            "records": {
                "users": [{"id": 101, "name": "Alice"}],
                "posts": [{"id": 1, "user_id": None, "title": "Post A"}],
            },
            "schema_ddl": TEST_SCHEMA_DDL,
        },
    )

    result_dict = await engine.execute_unit(unit)
    assert result_dict["success"] is True
    assert result_dict["records"]["posts"][0]["data"]["user_id"] == 101


@pytest.mark.asyncio
async def test_column_name_collision_scoping() -> None:
    """Test that a nullable foreign key column does not inherit NOT NULL constraints from a same-named column in another table."""
    engine = BindingEngine()

    schema_ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(50) NOT NULL
    );

    CREATE TABLE posts (
        id INT PRIMARY KEY,
        user_id INT, -- NULLABLE!
        title VARCHAR(100) NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE profiles (
        id INT PRIMARY KEY,
        user_id INT UNIQUE NOT NULL, -- NOT NULL!
        bio TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    records = {
        "users": [],
        "posts": [{"id": 1, "user_id": None, "title": "Nullable FK Post"}],
    }

    request = BindingRequest(records=records, schema_ddl=schema_ddl)
    result = await engine.bind(request)

    assert result.success
    assert len(result.errors) == 0
    assert result.statistics.unresolved_references_count == 1
    assert result.statistics.integrity_violations_count == 0
