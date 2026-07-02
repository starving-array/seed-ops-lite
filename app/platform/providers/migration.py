import contextlib
import json
import shutil
from pathlib import Path

from app.api.endpoints.schema.helpers import REDIS_KEY
from app.core.lifecycle.redis import redis_manager
from app.platform.container import get_persistence_provider
from app.platform.persistence.resolver import ProjectResolver
from app.platform.providers.sqlite_db import sqlite_db_manager


async def migrate_redis_to_sqlite() -> None:
    """Migrate legacy schema designer state from Redis to SQLite database on startup with safety backups."""
    db = get_persistence_provider()
    project_id = ProjectResolver.get_active_project_id()

    # Determine status first (Skip audit event check if already done)
    try:
        status = await db.get_app_setting("redis_migration_status")
        if status == "completed":
            return
    except Exception:
        # DB not initialized or offline
        return

    # Check if Redis connection pool can be initialized
    if redis_manager._pool is None:
        try:
            await redis_manager.connect()
        except Exception:
            # Skip if Redis offline
            return

    redis_online = await redis_manager.check_health()
    if not redis_online:
        return

    # Log Started audit event
    await db.log_audit_event("migration_started", "Redis to SQLite migration started")

    db_file = Path(sqlite_db_manager.db_path)
    backup_file = db_file.with_suffix(".sqlite.backup")
    backup_created = False

    try:
        # Create a database backup file
        if db_file.exists():
            shutil.copy2(db_file, backup_file)
            backup_created = True

        # Fetch legacy schema state key from Redis
        async with redis_manager.get_client() as client:
            raw_state = await client.get(REDIS_KEY)

        if raw_state:
            if isinstance(raw_state, bytes):
                raw_state = raw_state.decode("utf-8")

            schema_data = json.loads(raw_state)
            tables = schema_data.get("tables", [])
            relationships = schema_data.get("relationships", [])

            # Create project if missing
            if not await db.get_project(project_id):
                await db.create_project(project_id, "Default Project")

            # Write schema state to SQLite
            await db.save_schema(
                project_id=project_id,
                version=1,
                tables=tables,
                relationships=relationships,
            )

            # Read back from SQLite to verify content integrity
            migrated = await db.get_active_schema(project_id)
            if not migrated:
                raise ValueError("Read verification failed: migrated schema is None.")

            # Validate structural equivalence
            if len(migrated.get("tables", [])) != len(tables):
                raise ValueError(
                    f"Integrity check failed: expected {len(tables)} tables, got {len(migrated.get('tables', []))}."
                )

        # Mark migration complete in settings table
        await db.set_app_setting("redis_migration_status", "completed")

        # Log Completed audit event
        await db.log_audit_event(
            "migration_completed", "Redis to SQLite migration completed"
        )

        # Remove backup file on success
        if backup_created and backup_file.exists():
            backup_file.unlink()

    except Exception as e:
        # Restore from backup on failure
        if backup_created and backup_file.exists():
            try:
                # Terminate active engine connections before restoring
                sqlite_db_manager.shutdown()
                shutil.copy2(backup_file, db_file)
                sqlite_db_manager.initialize(run_migrations=True)
                backup_file.unlink()
            except Exception as restore_err:
                from app.core.logging.logging import logger
                from app.telemetry.events import EventID

                logger.error(
                    EventID.LOG_ERROR,
                    "SQLite database backup restoration failed during recovery",
                    error=str(restore_err),
                )

        # Log Failed audit event
        with contextlib.suppress(Exception):
            await db.log_audit_event(
                "migration_failed",
                "Redis to SQLite migration failed",
                {"error": str(e)},
            )

        from app.core.logging.logging import logger
        from app.telemetry.events import EventID

        logger.error(
            EventID.LOG_ERROR,
            "Idempotent Redis-to-SQLite migration failed",
            error=str(e),
        )
