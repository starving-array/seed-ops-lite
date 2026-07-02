import contextlib
import json
import sqlite3
import tempfile
import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import create_app
from app.platform.container import get_persistence_provider, register_platform_providers
from app.platform.persistence.resolver import ProjectResolver
from app.platform.providers.sqlite import SQLitePersistenceProvider
from app.platform.providers.sqlite_db import (
    DatabaseCorruptedException,
    DatabaseEngineException,
    DatabaseLockedException,
    SQLiteDatabaseManager,
)


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Fixture providing a unique temporary SQLite file path."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    import os

    os.close(fd)
    yield path
    p = Path(path)
    if p.exists():
        with contextlib.suppress(OSError):
            p.unlink()


def test_sqlite_initialization_and_migrations(temp_db_path: str) -> None:
    """Test SQLite connection manager initialization and automatic migrations."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    # Verify connection works and tables are created
    with db_manager.session() as session:
        version = session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert version is not None

    db_manager.shutdown()


@pytest.mark.asyncio
async def test_sqlite_transaction_rollback(temp_db_path: str) -> None:
    """Test that failed session transactions roll back changes completely."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    provider = SQLitePersistenceProvider()
    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager

    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    try:
        # Create project successfully
        project = await provider.create_project("proj_1", "Test Project")
        assert project["id"] == "proj_1"

        # Verify project is stored
        with db_manager.session() as session:
            res = session.execute(
                text("SELECT name FROM projects WHERE id='proj_1'")
            ).scalar()
            assert res == "Test Project"

        # 2. Rollback path (intentional exception)
        with pytest.raises(DatabaseEngineException), db_manager.session():
            # Raw insert bypassing provider check
            db_manager._session_factory().execute(
                text("INSERT INTO projects (id, name) VALUES ('proj_2', 'Temp')")
            )
            raise ValueError("Force transaction fail")

        # Verify proj_2 was not committed
        with db_manager.session() as session:
            res = session.execute(
                text("SELECT name FROM projects WHERE id='proj_2'")
            ).scalar()
            assert res is None

    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


def test_provider_di_registration() -> None:
    """Test that SQLitePersistenceProvider resolves correctly from the DI container."""
    register_platform_providers(persistence_factory=lambda: SQLitePersistenceProvider())
    provider = get_persistence_provider()
    assert isinstance(provider, SQLitePersistenceProvider)


def test_health_endpoint() -> None:
    """Test the extended /health endpoint responds with correct SQLite status schema."""
    from app.platform.providers.sqlite_db import sqlite_db_manager

    sqlite_db_manager.shutdown()

    with patch(
        "app.core.lifecycle.redis.redis_manager.check_health",
        new_callable=AsyncMock,
        return_value=True,
    ):
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "sqlite_status" in data
        status = data["sqlite_status"]
        assert status["status"] == "healthy"
        assert "database_path" in status
        assert "connection_status" in status
        assert "migration_version" in status


def test_sqlite_corrupted_database_detection(temp_db_path: str) -> None:
    """Test that a malformed database file raises DatabaseCorruptedException."""
    Path(temp_db_path).write_bytes(b"NOT A DATABASE FILE")

    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    with pytest.raises(DatabaseCorruptedException):
        db_manager.initialize(run_migrations=False)


def test_sqlite_locked_database_handling(temp_db_path: str) -> None:
    """Test that exclusive file locks raise DatabaseLockedException or DatabaseEngineException."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE dummy_lock (val INTEGER)")
    cursor.execute("PRAGMA locking_mode=EXCLUSIVE")
    cursor.execute("BEGIN EXCLUSIVE")

    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    import sqlalchemy

    db_manager._engine = sqlalchemy.create_engine(
        f"sqlite:///{temp_db_path}", connect_args={"timeout": 0.1}
    )
    db_manager._session_factory = sqlalchemy.orm.sessionmaker(
        bind=db_manager._engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    try:
        with pytest.raises((DatabaseLockedException, DatabaseEngineException)):
            db_manager.verify_health()
    finally:
        cursor.close()
        conn.close()
        db_manager.shutdown()


@pytest.mark.asyncio
async def test_project_crud(temp_db_path: str) -> None:
    """Test Project creation, read, and timestamp assignment operations."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    provider = SQLitePersistenceProvider()
    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    try:
        # Create
        created = await provider.create_project("proj_x", "Project X")
        assert created["id"] == "proj_x"
        assert created["name"] == "Project X"
        assert created["created_at"] is not None

        # Read
        retrieved = await provider.get_project("proj_x")
        assert retrieved is not None
        assert retrieved["name"] == "Project X"

        # Missing Project
        assert await provider.get_project("proj_missing") is None

    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


@pytest.mark.asyncio
async def test_schema_version_history(temp_db_path: str) -> None:
    """Test relational schema version history and active flag swaps."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    provider = SQLitePersistenceProvider()
    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    try:
        await provider.create_project("p1", "Project 1")

        # Save V1
        tables_v1 = [{"name": "users", "columns": []}]
        schema_v1 = await provider.save_schema("p1", 1, tables_v1, [])
        assert schema_v1["version"] == 1
        assert schema_v1["is_active"] == 1

        # Save V2 (should deactivate V1)
        tables_v2 = [
            {"name": "users", "columns": []},
            {"name": "orders", "columns": []},
        ]
        schema_v2 = await provider.save_schema("p1", 2, tables_v2, [])
        assert schema_v2["version"] == 2
        assert schema_v2["is_active"] == 1

        # Load Active Schema (should be V2)
        active = await provider.get_active_schema("p1")
        assert active is not None
        assert active["version"] == 2
        assert len(active["tables"]) == 2

    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


@pytest.mark.asyncio
async def test_settings_persistence(temp_db_path: str) -> None:
    """Test application configurations and preferences set/get settings."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    provider = SQLitePersistenceProvider()
    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    try:
        await provider.set_app_setting("preferences.theme", "dark")
        val = await provider.get_app_setting("preferences.theme")
        assert val == "dark"

        # Overwrite setting
        await provider.set_app_setting("preferences.theme", "light")
        val = await provider.get_app_setting("preferences.theme")
        assert val == "light"

    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


def test_sqlite_concurrent_writes(temp_db_path: str) -> None:
    """Test simultaneous writes concurrency safety in WAL mode."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    errors = []

    def worker(i: int) -> None:
        try:
            with db_manager.session() as s:
                s.execute(
                    text(
                        "INSERT INTO app_settings (key, value, updated_at) VALUES (:key, :value, datetime('now'))"
                    ),
                    {"key": f"key_{i}", "value": f"val_{i}"},
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    with db_manager.session() as s:
        count = s.execute(text("SELECT count(*) FROM app_settings")).scalar()
        assert count == 15
    db_manager.shutdown()


def test_sqlite_concurrent_reads(temp_db_path: str) -> None:
    """Test simultaneous reads concurrency safety in WAL mode."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    with db_manager.session() as s:
        s.execute(
            text(
                "INSERT INTO app_settings (key, value, updated_at) VALUES ('theme', 'dark', datetime('now'))"
            )
        )

    errors = []

    def worker() -> None:
        try:
            with db_manager.session() as s:
                val = s.execute(
                    text("SELECT value FROM app_settings WHERE key='theme'")
                ).scalar()
                assert val == "dark"
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    db_manager.shutdown()


def test_sqlite_restart_persistence(temp_db_path: str) -> None:
    """Test that data remains persisted across connection restarts."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    with db_manager.session() as s:
        s.execute(
            text(
                "INSERT INTO app_settings (key, value, updated_at) VALUES ('mode', 'lite', datetime('now'))"
            )
        )
    db_manager.shutdown()

    # Re-initialize DB Manager on the same path
    db_manager_2 = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager_2.initialize(run_migrations=True)

    with db_manager_2.session() as s:
        val = s.execute(
            text("SELECT value FROM app_settings WHERE key='mode'")
        ).scalar()
        assert val == "lite"
    db_manager_2.shutdown()


@pytest.mark.asyncio
async def test_redis_to_sqlite_migration(temp_db_path: str) -> None:
    """Test idempotent migration from Redis to SQLite database."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    # Mock Redis client, pool, and get_client method
    mock_redis_client = AsyncMock()
    legacy_schema = {
        "tables": [{"id": "t1", "name": "legacy_users", "columns": []}],
        "relationships": [],
    }
    mock_redis_client.get.return_value = json.dumps(legacy_schema).encode("utf-8")

    from app.core.lifecycle.redis import redis_manager

    original_pool = redis_manager._pool
    original_get_client = redis_manager.get_client

    mock_pool = MagicMock()
    redis_manager._pool = mock_pool

    mock_get_client = MagicMock()
    mock_get_client.return_value.__aenter__.return_value = mock_redis_client
    redis_manager.get_client = mock_get_client

    try:
        with patch(
            "app.core.lifecycle.redis.redis_manager.check_health",
            new_callable=AsyncMock,
            return_value=True,
        ):
            from app.platform.providers.migration import migrate_redis_to_sqlite

            # Run migration first time
            await migrate_redis_to_sqlite()

        # Verify that SQLite persistence matches legacy data
        provider = SQLitePersistenceProvider()
        active_schema = await provider.get_active_schema(
            ProjectResolver.get_active_project_id()
        )
        assert active_schema is not None
        assert active_schema["tables"][0]["name"] == "legacy_users"

        # Verify migration status set
        status = await provider.get_app_setting("redis_migration_status")
        assert status == "completed"

        # Verify Started and Completed audit events logged!
        with db_manager.session() as s:
            started_cnt = s.execute(
                text(
                    "SELECT count(*) FROM audit_logs WHERE event_type='migration_started'"
                )
            ).scalar()
            completed_cnt = s.execute(
                text(
                    "SELECT count(*) FROM audit_logs WHERE event_type='migration_completed'"
                )
            ).scalar()
            assert started_cnt == 1
            assert completed_cnt == 1

        # Modify SQLite data manually
        with db_manager.session() as s:
            s.execute(text("UPDATE schemas SET tables_json='[]'"))

        # Run migration second time (idempotency check)
        with patch(
            "app.core.lifecycle.redis.redis_manager.check_health",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await migrate_redis_to_sqlite()

        # Schema should NOT be overwritten because status is "completed"
        active_schema_2 = await provider.get_active_schema(
            ProjectResolver.get_active_project_id()
        )
        assert active_schema_2 is not None
        assert len(active_schema_2["tables"]) == 0

    finally:
        redis_manager._pool = original_pool
        redis_manager.get_client = original_get_client
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


def test_project_resolver() -> None:
    """Test ProjectResolver active ID matches 'default'."""
    assert ProjectResolver.get_active_project_id() == "default"


@pytest.mark.asyncio
async def test_migration_backup_and_recovery(temp_db_path: str) -> None:
    """Test database backup creation, failure restoration, and audit reporting."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    # Write a pre-migration dummy setting
    with db_manager.session() as s:
        s.execute(
            text(
                "INSERT INTO app_settings (key, value, updated_at) VALUES ('version', 'pre-migration', datetime('now'))"
            )
        )

    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    # Mock Redis client
    mock_redis_client = AsyncMock()
    legacy_schema = {
        "tables": [
            {"id": "t1", "name": "users", "columns": []},
            {"id": "t2", "name": "orders", "columns": []},
        ],
        "relationships": [],
    }
    mock_redis_client.get.return_value = json.dumps(legacy_schema).encode("utf-8")

    from app.core.lifecycle.redis import redis_manager

    original_pool = redis_manager._pool
    original_get_client = redis_manager.get_client

    mock_pool = MagicMock()
    redis_manager._pool = mock_pool
    mock_get_client = MagicMock()
    mock_get_client.return_value.__aenter__.return_value = mock_redis_client
    redis_manager.get_client = mock_get_client

    try:
        # Mock get_active_schema return count to trigger verification check failure
        with (
            patch(
                "app.core.lifecycle.redis.redis_manager.check_health",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.platform.providers.sqlite.SQLitePersistenceProvider.get_active_schema",
                new_callable=AsyncMock,
                return_value={"tables": []},
            ),
        ):
            from app.platform.providers.migration import migrate_redis_to_sqlite

            await migrate_redis_to_sqlite()

        # Database must automatically restore setting to pre-migration state
        with db_manager.session() as s:
            val = s.execute(
                text("SELECT value FROM app_settings WHERE key='version'")
            ).scalar()
            assert val == "pre-migration"

        # Check migration_failed audit event was logged
        with db_manager.session() as s:
            failed_cnt = s.execute(
                text(
                    "SELECT count(*) FROM audit_logs WHERE event_type='migration_failed'"
                )
            ).scalar()
            assert failed_cnt > 0

    finally:
        redis_manager._pool = original_pool
        redis_manager.get_client = original_get_client
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


def test_health_endpoint_diagnostics() -> None:
    """Test extended health diagnostics response schema fields."""
    from app.platform.providers.sqlite_db import sqlite_db_manager

    sqlite_db_manager.shutdown()

    with patch(
        "app.core.lifecycle.redis.redis_manager.check_health",
        new_callable=AsyncMock,
        return_value=True,
    ):
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "sqlite_status" in data
        status = data["sqlite_status"]
        assert status["status"] == "healthy"
        assert status["initialized"] is True
        assert status["migration_status"] in ("completed", "pending")
        assert "pending_migrations" in status
        assert "last_successful_migration_at" in status


@pytest.mark.asyncio
async def test_uow_commit(temp_db_path: str) -> None:
    """Test that Unit of Work transaction commits persist values successfully."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    try:
        provider = SQLitePersistenceProvider()
        async with provider.unit_of_work() as uow:
            await uow.projects.create_project("uow_1", "UOW Project")
            await uow.commit()

        # Verify committed value
        async with provider.unit_of_work() as uow:
            proj = await uow.projects.get_project("uow_1")
            assert proj is not None
            assert proj["name"] == "UOW Project"
    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


@pytest.mark.asyncio
async def test_uow_rollback(temp_db_path: str) -> None:
    """Test that exceptions inside Unit of Work roll back modifications."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    try:
        provider = SQLitePersistenceProvider()
        with contextlib.suppress(ValueError):
            async with provider.unit_of_work() as uow:
                await uow.projects.create_project("uow_2", "Should roll back")
                raise ValueError("Fail transaction")

        # Verify not committed
        async with provider.unit_of_work() as uow:
            proj = await uow.projects.get_project("uow_2")
            assert proj is None
    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


@pytest.mark.asyncio
async def test_optimistic_locking_concurrency(temp_db_path: str) -> None:
    """Test that Project entity version attributes trigger ConcurrencyError conflicts."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    try:
        provider = SQLitePersistenceProvider()
        # 1. Create project (version = 1)
        async with provider.unit_of_work() as uow:
            proj = await uow.projects.create_project("proj_c", "Proj C")
            assert proj["version"] == 1
            await uow.commit()

        # 2. Update successfully (advances version to 2)
        async with provider.unit_of_work() as uow:
            proj_up = await uow.projects.update_project_name(
                "proj_c", "Proj C Updated", current_version=1
            )
            assert proj_up["version"] == 2
            await uow.commit()

        # 3. Conflict trigger (current_version mismatch)
        from app.platform.persistence.exceptions import ConcurrencyError

        with pytest.raises(ConcurrencyError):
            async with provider.unit_of_work() as uow:
                await uow.projects.update_project_name(
                    "proj_c", "Proj Conflict", current_version=1
                )
    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()


def test_exception_mapping() -> None:
    """Test raw SQLAlchemy exception mappings to platform specific error classes."""
    from sqlalchemy.exc import IntegrityError, OperationalError

    from app.platform.persistence.exceptions import (
        DatabaseLockedError,
        ValidationError,
        map_persistence_exception,
    )

    # Lock error mapping
    op_err = OperationalError("select", {}, Exception("database is locked"))
    mapped = map_persistence_exception(op_err)
    assert isinstance(mapped, DatabaseLockedError)

    # Constraint integrity mapping
    int_err = IntegrityError(
        "insert", {}, Exception("foreign key constraint violation")
    )
    mapped_int = map_persistence_exception(int_err)
    assert isinstance(mapped_int, ValidationError)


@pytest.mark.asyncio
async def test_operational_persistence_suite(temp_db_path: str) -> None:
    """Test full cycle of operational entities: jobs, validations, exports, metadata, issues, audits, and domain events."""
    db_manager = SQLiteDatabaseManager(db_path=temp_db_path)
    db_manager.initialize(run_migrations=True)

    from app.platform.providers import sqlite, sqlite_db

    original_db = sqlite_db.sqlite_db_manager
    original_sqlite_db = sqlite.sqlite_db_manager
    sqlite_db.sqlite_db_manager = db_manager
    sqlite.sqlite_db_manager = db_manager

    # Set up domain event tracking callback
    events_dispatched = []

    def event_listener(event_name: str, payload: dict[str, Any]) -> None:
        events_dispatched.append((event_name, payload))

    from app.platform.providers.sqlite import DomainEventDispatcher

    DomainEventDispatcher.register(event_listener)

    try:
        provider = SQLitePersistenceProvider()

        # 1. Project
        async with provider.unit_of_work() as uow:
            await uow.projects.create_project("proj_op", "Operational Project")
            await uow.commit()

        # 2. Schema
        async with provider.unit_of_work() as uow:
            schema = await uow.schemas.save_schema("proj_op", 1, [{"name": "t1"}], [])
            await uow.commit()
            schema_id = schema["id"]

        # 3. Job
        async with provider.unit_of_work() as uow:
            await uow.jobs.create_job("job_op", "proj_op", "validation", "pending")
            await uow.commit()

        # 4. Job update
        async with provider.unit_of_work() as uow:
            await uow.jobs.update_job_status(
                "job_op", "completed", 1.0, 5.2, "Passed", None, {"extra": "info"}
            )
            await uow.commit()

        # 5. Validation Run
        async with provider.unit_of_work() as uow:
            await uow.validations.log_validation_run(schema_id, "Passed", [], 250.0)
            await uow.commit()

        # 6. Export Log
        async with provider.unit_of_work() as uow:
            await uow.exports.log_export(
                "exp_op", "job_op", "csv", "/path/file.csv", "sha256sum", 1024
            )
            await uow.commit()

        # 7. Metadata stats
        async with provider.unit_of_work() as uow:
            await uow.metadata.save_metadata("job_op", 100, {"t1": 100}, "/path/")
            await uow.commit()

        # 8. Caretaker Issues and status transitions
        async with provider.unit_of_work() as uow:
            await uow.issues.log_caretaker_issue(
                "issue_op",
                "performance",
                "high",
                "monitoring",
                "sqlite",
                "Optimize connection timeout",
            )
            await uow.commit()

        async with provider.unit_of_work() as uow:
            await uow.issues.resolve_caretaker_issue(
                "issue_op", "Set timeout limit to 15s"
            )
            await uow.commit()

        # 9. Audit Logging
        async with provider.unit_of_work() as uow:
            await uow.audits.log_audit_event(
                "migration_completed", "migrate_sqlite", {"status": "success"}
            )
            await uow.commit()

        # --- Verifications ---
        async with provider.unit_of_work() as uow:
            # Job
            job = await uow.jobs.get_job("job_op")
            assert job is not None
            assert job["status"] == "completed"

            # Export
            export = await uow.exports.get_export("exp_op")
            assert export is not None
            assert export["format"] == "csv"

            # Metadata
            meta = await uow.metadata.get_metadata("job_op")
            assert meta is not None
            assert meta["total_rows"] == 100

        # Assert correct domain events were emitted!
        event_names = [evt[0] for evt in events_dispatched]
        assert "project_created" in event_names
        assert "schema_saved" in event_names
        assert "job_created" in event_names
        assert "job_status_updated" in event_names
        assert "dataset_exported" in event_names
        assert "metadata_saved" in event_names
        assert "caretaker_issue_raised" in event_names
        assert "caretaker_issue_resolved" in event_names

    finally:
        sqlite_db.sqlite_db_manager = original_db
        sqlite.sqlite_db_manager = original_sqlite_db
        db_manager.shutdown()
        DomainEventDispatcher._listeners.remove(event_listener)
