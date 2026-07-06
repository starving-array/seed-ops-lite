from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class ProjectRepository(ABC):
    """Repository interface for project workspace metadata."""

    @abstractmethod
    async def create_project(
        self,
        project_id: str,
        name: str,
        description: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Create a new project workspace record."""
        pass

    @abstractmethod
    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Retrieve details of a single project."""
        pass

    @abstractmethod
    async def list_projects(self) -> list[dict[str, Any]]:
        """Retrieve list of all projects."""
        pass


class SchemaRepository(ABC):
    """Repository interface for database schemas."""

    @abstractmethod
    async def save_schema(
        self, project_id: str, version: int, tables: list[Any], relationships: list[Any]
    ) -> dict[str, Any]:
        """Save a new version of the schema design."""
        pass

    @abstractmethod
    async def get_active_schema(self, project_id: str) -> dict[str, Any] | None:
        """Load the active schema model for a project."""
        pass

    @abstractmethod
    async def deactivate_schema(self, project_id: str) -> None:
        """Deactivate the active schema design."""
        pass


class JobRepository(ABC):
    """Repository interface for background validation and generation jobs."""

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


class ValidationRepository(ABC):
    """Repository interface for diagnostic validation results."""

    @abstractmethod
    async def log_validation_run(
        self, schema_id: str, status: str, issues: list[Any], duration_ms: float
    ) -> dict[str, Any]:
        """Record diagnostic validation results."""
        pass


class ExportRepository(ABC):
    """Repository interface for dataset export actions."""

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


class DatasetMetadataRepository(ABC):
    """Repository interface for persistent dataset metadata stats."""

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


class SettingsRepository(ABC):
    """Repository interface for platform and application configurations."""

    @abstractmethod
    async def set_app_setting(self, key: str, value: str) -> None:
        """Update a global application config settings value."""
        pass

    @abstractmethod
    async def get_app_setting(self, key: str) -> str | None:
        """Retrieve a global application setting value."""
        pass


class IssueRepository(ABC):
    """Repository interface for caretaker maintenance checks and issues."""

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
        """Mark a caretaker issue as resolved."""
        pass


class AuditRepository(ABC):
    """Repository interface for audit event logs."""

    @abstractmethod
    async def log_audit_event(
        self, event_type: str, action: str, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Log audit event to SQLite database or memory."""
        pass
