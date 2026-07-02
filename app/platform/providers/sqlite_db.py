import contextlib
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from alembic.config import Config
from app.platform.configuration.settings import platform_settings


class DatabaseEngineException(Exception):
    """Base exception for all SQLite database operational failures."""

    pass


class DatabaseLockedException(DatabaseEngineException):
    """Raised when the database remains locked beyond the busy_timeout threshold."""

    pass


class DatabaseCorruptedException(DatabaseEngineException):
    """Raised when SQLite file integrity check fails or the file is malformed."""

    pass


class SQLiteDatabaseManager:
    """Manages the connection lifecycles, session factories, and health checks for SQLite."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or platform_settings.SQLITE_DB_PATH
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def initialize(self, run_migrations: bool = True) -> None:
        """Initialize connection engine, create storage directories, and run health check."""
        if self._engine:
            return
        try:
            # Ensure parent directories exist
            from pathlib import Path

            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            db_url = f"sqlite:///{self.db_path}"
            self._engine = create_engine(
                db_url,
                connect_args={"timeout": platform_settings.SQLITE_TIMEOUT_SECONDS},
                pool_size=platform_settings.SQLITE_POOL_SIZE,
                max_overflow=10,
            )

            # Enable foreign key validation and WAL mode on connections
            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )

            # Perform liveness and integrity validation check
            self.verify_health()

            # Execute pending migrations programmatically
            if run_migrations:
                self.run_db_migrations()

        except (DatabaseError, sqlite3.DatabaseError) as e:
            raise DatabaseCorruptedException(
                f"Database file is malformed or corrupted: {e}"
            ) from e
        except DatabaseEngineException:
            raise
        except Exception as e:
            raise DatabaseEngineException(
                f"Failed to initialize SQLite database: {e}"
            ) from e

    def verify_health(self) -> None:
        """Execute diagnostic checks to verify DB file is not locked or corrupted."""
        if not self._engine:
            raise DatabaseEngineException("Database manager is not initialized.")
        try:
            with self._engine.connect() as conn:
                # Perform basic schema read and write test
                res = conn.execute(text("PRAGMA integrity_check")).scalar()
                if res != "ok":
                    raise DatabaseCorruptedException(
                        f"SQLite PRAGMA integrity_check failed: {res}"
                    )
        except OperationalError as e:
            if "locked" in str(e).lower():
                raise DatabaseLockedException(
                    "Database is locked by another process."
                ) from e
            raise DatabaseEngineException(f"Operational database error: {e}") from e
        except DatabaseError as e:
            raise DatabaseCorruptedException(
                f"Corrupted database disk image: {e}"
            ) from e

    def run_db_migrations(self) -> None:
        """Execute all pending Alembic schema migrations dynamically."""
        try:
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
            command.upgrade(alembic_cfg, "head")
        except Exception as e:
            raise DatabaseEngineException(
                f"Failed to execute database migrations: {e}"
            ) from e

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional boundary context manager supporting automatic commit and rollback."""
        if not self._session_factory:
            raise DatabaseEngineException("Database manager has not been initialized.")

        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except OperationalError as e:
            session.rollback()
            if "locked" in str(e).lower():
                raise DatabaseLockedException(
                    "Transaction aborted due to locked database state."
                ) from e
            raise DatabaseEngineException(
                f"Operational failure during transaction: {e}"
            ) from e
        except Exception as e:
            session.rollback()
            raise DatabaseEngineException(
                f"Transaction failed, changes rolled back: {e}"
            ) from e
        finally:
            session.close()

    def shutdown(self) -> None:
        """Close connection pools and clean up active handles."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def get_migration_info(self) -> dict[str, Any]:
        """Retrieve migration versions, status, and check if any are pending."""
        if not self._engine:
            return {
                "initialized": False,
                "migration_status": "uninitialized",
                "current_schema_version": "none",
                "pending_migrations": [],
                "last_successful_migration_at": None,
            }

        current_version = None
        last_migration_time = None
        with contextlib.suppress(Exception), self.session() as s:
            current_version = s.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
            # Query metadata for updated_at timestamp
            meta = s.execute(
                text(
                    "SELECT updated_at FROM system_metadata ORDER BY updated_at DESC LIMIT 1"
                )
            ).scalar()
            if meta:
                last_migration_time = str(meta)

        pending = []
        with contextlib.suppress(Exception):
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            alembic_cfg = Config("alembic.ini")
            script = ScriptDirectory.from_config(alembic_cfg)
            all_revisions = [rev.revision for rev in script.walk_revisions()]
            if current_version:
                for rev in all_revisions:
                    if rev == current_version:
                        break
                    pending.append(rev)
            else:
                pending = all_revisions

        migration_status = "pending" if pending else "completed"

        return {
            "initialized": True,
            "migration_status": migration_status,
            "current_schema_version": (
                str(current_version) if current_version else "none"
            ),
            "pending_migrations": pending,
            "last_successful_migration_at": last_migration_time,
        }


# Global singleton instance
sqlite_db_manager = SQLiteDatabaseManager()
