from sqlalchemy.exc import IntegrityError, OperationalError


class PersistenceError(Exception):
    """Base exception class for all platform persistence and database operations."""

    pass


class DatabaseLockedError(PersistenceError):
    """Raised when the database connection remains locked by another process."""

    pass


class MigrationError(PersistenceError):
    """Raised when schema migrations encounter a structural database error."""

    pass


class EntityNotFoundError(PersistenceError):
    """Raised when a requested resource (like project or setting) is missing."""

    pass


class ConcurrencyError(PersistenceError):
    """Raised when an optimistic concurrency update conflict is detected."""

    pass


class ValidationError(PersistenceError):
    """Raised when a schema validation check fails or structure is invalid."""

    pass


def map_persistence_exception(exc: Exception) -> Exception:
    """Map raw DBAPI/SQLAlchemy exceptions to platform persistence exception classes."""
    if isinstance(exc, PersistenceError):
        return exc

    err_str = str(exc).lower()

    if isinstance(exc, OperationalError) and "locked" in err_str:
        return DatabaseLockedError("Database is currently locked by another process.")

    if isinstance(exc, IntegrityError):
        if "foreign key" in err_str:
            return ValidationError("Foreign key constraint violation.")
        return ValidationError("Database integrity check failed.")

    return PersistenceError(f"Database operation failed: {exc}")
