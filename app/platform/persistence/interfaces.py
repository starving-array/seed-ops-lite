from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from app.platform.persistence.repositories import (
    AuditRepository,
    DatasetMetadataRepository,
    ExportRepository,
    IssueRepository,
    JobRepository,
    ProjectRepository,
    SchemaRepository,
    SettingsRepository,
    ValidationRepository,
)


class UnitOfWork(ABC):
    """Abstract interface defining the Unit of Work pattern for managing transaction boundaries."""

    @property
    @abstractmethod
    def projects(self) -> ProjectRepository:
        """Access the project repository namespace."""
        pass

    @property
    @abstractmethod
    def schemas(self) -> SchemaRepository:
        """Access the schema repository namespace."""
        pass

    @property
    @abstractmethod
    def jobs(self) -> JobRepository:
        """Access the jobs repository namespace."""
        pass

    @property
    @abstractmethod
    def validations(self) -> ValidationRepository:
        """Access the validations repository namespace."""
        pass

    @property
    @abstractmethod
    def exports(self) -> ExportRepository:
        """Access the exports repository namespace."""
        pass

    @property
    @abstractmethod
    def metadata(self) -> DatasetMetadataRepository:
        """Access the dataset metadata repository namespace."""
        pass

    @property
    @abstractmethod
    def settings(self) -> SettingsRepository:
        """Access the settings repository namespace."""
        pass

    @property
    @abstractmethod
    def issues(self) -> IssueRepository:
        """Access the caretaker issues repository namespace."""
        pass

    @property
    @abstractmethod
    def audits(self) -> AuditRepository:
        """Access the audit logging repository namespace."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction to the database."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current active transaction."""
        pass

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        """Start the transactional boundary."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the transactional boundary, rolling back if exceptions occurred."""
        pass


class PersistenceProvider(ABC):
    """Abstract interface defining standard database read/write persistence operations."""

    @abstractmethod
    def unit_of_work(self) -> UnitOfWork:
        """Return a Unit of Work instance managing one transaction."""
        pass

    @abstractmethod
    async def create_project(self, project_id: str, name: str) -> dict[str, Any]:
        """Create a new workspace project record."""
        pass

    @abstractmethod
    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Retrieve details of a single project."""
        pass

    @abstractmethod
    async def save_schema(
        self, project_id: str, version: int, tables: list[Any], relationships: list[Any]
    ) -> dict[str, Any]:
        """Save a new version of the relational database schema design."""
        pass

    @abstractmethod
    async def get_active_schema(self, project_id: str) -> dict[str, Any] | None:
        """Load the active schema model for a project."""
        pass

    @abstractmethod
    async def create_job(
        self, job_id: str, project_id: str, job_type: str, status: str
    ) -> dict[str, Any]:
        """Insert a background task execution job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Retrieve execution job metadata and timers."""
        pass

    @abstractmethod
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: float,
        duration: float = 0.0,
        result_summary: str | None = None,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Update job progress counters, status flags, and statistics."""
        pass

    @abstractmethod
    async def list_jobs(
        self, project_id: str | None = None
    ) -> Sequence[dict[str, Any]]:
        """List background jobs, optionally filtering by project."""
        pass

    @abstractmethod
    async def log_validation_run(
        self, schema_id: str, status: str, issues: list[Any], duration_ms: float
    ) -> dict[str, Any]:
        """Record diagnostic validation results for audits."""
        pass

    @abstractmethod
    async def log_export(
        self,
        export_id: str,
        job_id: str,
        format_name: str,
        file_path: str,
        checksum: str,
        file_size_bytes: int,
    ) -> dict[str, Any]:
        """Record a successful file export outcome."""
        pass

    @abstractmethod
    async def get_export(self, export_id: str) -> dict[str, Any] | None:
        """Retrieve details of a logged export entry."""
        pass

    @abstractmethod
    async def save_metadata(
        self,
        job_id: str,
        total_rows: int,
        table_stats: dict[str, Any],
        folder_path: str,
    ) -> dict[str, Any]:
        """Persist metadata statistics for a generated dataset."""
        pass

    @abstractmethod
    async def get_metadata(self, job_id: str) -> dict[str, Any] | None:
        """Retrieve dataset metadata stats associated with a job."""
        pass

    @abstractmethod
    async def set_app_setting(self, key: str, value: str) -> None:
        """Update a global application config settings value."""
        pass

    @abstractmethod
    async def get_app_setting(self, key: str) -> str | None:
        """Retrieve a global application setting value."""
        pass

    @abstractmethod
    async def log_caretaker_issue(
        self,
        issue_id: str,
        category: str,
        severity: str,
        source: str,
        affected_component: str,
        suggested_fix: str,
    ) -> dict[str, Any]:
        """Report a newly detected caretaker maintenance issue."""
        pass

    @abstractmethod
    async def resolve_caretaker_issue(
        self, issue_id: str, resolution_notes: str
    ) -> None:
        """Mark a caretaker issue as successfully healed."""
        pass

    @abstractmethod
    async def log_audit_event(
        self, event_type: str, action: str, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Record an audit trail event log entry."""
        pass
