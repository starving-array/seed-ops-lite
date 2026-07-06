import datetime
import json
import uuid
from collections.abc import Sequence
from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.core.logging.logging import logger
from app.platform.persistence.exceptions import (
    ConcurrencyError,
    EntityNotFoundError,
    PersistenceError,
    map_persistence_exception,
)
from app.platform.persistence.interfaces import PersistenceProvider, UnitOfWork
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
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.platform.providers.sqlite_models import (
    AppSetting,
    AuditLog,
    DatasetMetadata,
    ExportHistory,
    Issue,
    IssueEvent,
    Job,
    Project,
    Schema,
    ValidationHistory,
)
from app.telemetry.events import EventID


class DomainEventDispatcher:
    """Lightweight dispatch hub for platform business domain events."""

    _listeners: ClassVar[list[Any]] = []

    @classmethod
    def register(cls, listener: Any) -> None:
        """Register a handler callback for domain events."""
        cls._listeners.append(listener)

    @classmethod
    def dispatch(cls, event_name: str, payload: dict[str, Any]) -> None:
        """Log and dispatch event signals to registered callback channels."""
        logger.info(
            EventID.LOG_INFO,
            f"Domain Event Dispatched: {event_name}",
            details={"payload": payload},
        )
        for listener in cls._listeners:
            try:
                listener(event_name, payload)
            except Exception as e:
                logger.error(
                    EventID.LOG_ERROR,
                    f"Error running listener for domain event {event_name}: {e}",
                )


class SQLiteProjectRepository(ProjectRepository):
    """SQLite implementation of project CRUD workspace actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def create_project(
        self,
        project_id: str,
        name: str,
        description: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        try:
            project = Project(
                id=project_id,
                name=name,
                description=description,
                status=status or "pending",
                version=1,
            )
            self.session.add(project)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "project_created", {"project_id": project_id, "name": name}
            )
            return {
                "id": project.id,
                "name": project.name,
                "description": project.description or "",
                "status": project.status or "pending",
                "tables": 0,
                "version": project.version,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        try:
            project = self.session.execute(
                select(Project).where(Project.id == project_id)
            ).scalar_one_or_none()
            if not project:
                return None
            active_schema = self.session.execute(
                select(Schema).where(
                    Schema.project_id == project.id, Schema.is_active == 1
                )
            ).scalar_one_or_none()
            tables_count = 0
            if active_schema:
                try:
                    tables_data = json.loads(active_schema.tables_json)
                    tables_count = len(tables_data)
                except Exception:  # noqa: S110
                    pass
            return {
                "id": project.id,
                "name": project.name,
                "description": project.description or "",
                "status": project.status or "pending",
                "tables": tables_count,
                "version": project.version,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def list_projects(self) -> list[dict[str, Any]]:
        try:
            projects = self.session.execute(select(Project)).scalars().all()
            res = []
            for p in projects:
                active_schema = self.session.execute(
                    select(Schema).where(
                        Schema.project_id == p.id, Schema.is_active == 1
                    )
                ).scalar_one_or_none()
                tables_count = 0
                if active_schema:
                    try:
                        tables_data = json.loads(active_schema.tables_json)
                        tables_count = len(tables_data)
                    except Exception:  # noqa: S110
                        pass
                res.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description or "",
                        "status": p.status or "pending",
                        "tables": tables_count,
                        "version": p.version,
                        "created_at": p.created_at,
                        "updated_at": p.updated_at,
                    }
                )
            return res
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def update_project_name(
        self, project_id: str, name: str, current_version: int
    ) -> dict[str, Any]:
        """Update project name using optimistic locking conflict check."""
        try:
            project = self.session.execute(
                select(Project).where(Project.id == project_id)
            ).scalar_one_or_none()
            if not project:
                raise EntityNotFoundError(f"Project {project_id} not found.")

            if project.version != current_version:
                raise ConcurrencyError(
                    f"Optimistic lock check failed: expected version {current_version}, got {project.version}."
                )

            project.name = name
            project.version += 1
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "project_updated",
                {"project_id": project_id, "version": project.version},
            )
            return {
                "id": project.id,
                "name": project.name,
                "version": project.version,
                "updated_at": project.updated_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteSchemaRepository(SchemaRepository):
    """SQLite implementation of schema version CRUD actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def save_schema(
        self, project_id: str, version: int, tables: list[Any], relationships: list[Any]
    ) -> dict[str, Any]:
        try:
            # Deactivate previous schemas in a single transactional query
            self.session.query(Schema).filter(
                Schema.project_id == project_id, Schema.is_active == 1
            ).update({Schema.is_active: 0})

            schema = Schema(
                id=f"sch_{project_id}_v{version}_{str(uuid.uuid4())[:8]}",
                project_id=project_id,
                version=version,
                tables_json=json.dumps(tables),
                relationships_json=json.dumps(relationships),
                is_active=1,
            )
            self.session.add(schema)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "schema_saved", {"project_id": project_id, "version": version}
            )
            return {
                "id": schema.id,
                "project_id": schema.project_id,
                "version": schema.version,
                "tables": tables,
                "relationships": relationships,
                "is_active": schema.is_active,
                "created_at": schema.created_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def get_active_schema(self, project_id: str) -> dict[str, Any] | None:
        try:
            schema = self.session.execute(
                select(Schema).where(
                    Schema.project_id == project_id, Schema.is_active == 1
                )
            ).scalar_one_or_none()
            if not schema:
                return None
            return {
                "id": schema.id,
                "project_id": schema.project_id,
                "version": schema.version,
                "tables": json.loads(schema.tables_json),
                "relationships": json.loads(schema.relationships_json),
                "is_active": schema.is_active,
                "created_at": schema.created_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def deactivate_schema(self, project_id: str) -> None:
        try:
            self.session.query(Schema).filter(
                Schema.project_id == project_id, Schema.is_active == 1
            ).update({Schema.is_active: 0})
            self.session.flush()
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteSettingsRepository(SettingsRepository):
    """SQLite implementation of system app settings store."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def set_app_setting(self, key: str, value: str) -> None:
        try:
            stmt = insert(AppSetting).values(
                key=key, value=value, updated_at=datetime.datetime.utcnow()
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[AppSetting.key],
                set_={"value": value, "updated_at": datetime.datetime.utcnow()},
            )
            self.session.execute(stmt)
            self.session.flush()
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def get_app_setting(self, key: str) -> str | None:
        try:
            return self.session.execute(
                select(AppSetting.value).where(AppSetting.key == key)
            ).scalar()
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteJobRepository(JobRepository):
    """SQLite implementation for Job execution state actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def create_job(
        self, job_id: str, project_id: str, job_type: str, status: str
    ) -> dict[str, Any]:
        try:
            job = Job(id=job_id, project_id=project_id, type=job_type, status=status)
            self.session.add(job)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "job_created",
                {"job_id": job_id, "project_id": project_id, "type": job_type},
            )
            return {
                "id": job.id,
                "project_id": job.project_id,
                "type": job.type,
                "status": job.status,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        try:
            job = self.session.execute(
                select(Job).where(Job.id == job_id)
            ).scalar_one_or_none()
            if not job:
                return None
            return {
                "id": job.id,
                "jobId": job.id,
                "project_id": job.project_id,
                "type": job.type,
                "status": job.status,
                "progress": job.progress,
                "startedAt": (
                    job.started_at.isoformat() + "Z" if job.started_at else None
                ),
                "finishedAt": (
                    job.finished_at.isoformat() + "Z" if job.finished_at else None
                ),
                "duration": job.duration,
                "resultSummary": job.result_summary,
                "errorMessage": job.error_message,
                "details": json.loads(job.details_json) if job.details_json else {},
                "owner": None,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

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
        try:
            import datetime as _dt

            job = self.session.execute(
                select(Job).where(Job.id == job_id)
            ).scalar_one_or_none()
            if job:
                job.status = status
                job.progress = progress
                job.duration = duration
                job.result_summary = result_summary
                job.error_message = error_message
                job.details_json = json.dumps(details) if details else None
                if (
                    status in ("Completed", "Failed", "Cancelled")
                    and job.finished_at is None
                ):
                    job.finished_at = _dt.datetime.utcnow()
                self.session.flush()
                DomainEventDispatcher.dispatch(
                    "job_status_updated", {"job_id": job_id, "status": status}
                )
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def list_jobs(
        self, project_id: str | None = None
    ) -> Sequence[dict[str, Any]]:
        try:
            stmt = select(Job).order_by(Job.started_at.desc())
            if project_id:
                stmt = stmt.where(Job.project_id == project_id)
            jobs = self.session.execute(stmt).scalars().all()
            return [
                {
                    "id": job.id,
                    "jobId": job.id,
                    "project_id": job.project_id,
                    "type": job.type,
                    "status": job.status,
                    "progress": job.progress,
                    "startedAt": (
                        job.started_at.isoformat() + "Z" if job.started_at else None
                    ),
                    "finishedAt": (
                        job.finished_at.isoformat() + "Z" if job.finished_at else None
                    ),
                    "duration": job.duration,
                    "resultSummary": job.result_summary,
                    "errorMessage": job.error_message,
                    "details": json.loads(job.details_json) if job.details_json else {},
                    "owner": None,
                }
                for job in jobs
            ]
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteValidationRepository(ValidationRepository):
    """SQLite implementation of schema validation runs diagnostics trail."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def log_validation_run(
        self, schema_id: str, status: str, issues: list[Any], duration_ms: float
    ) -> dict[str, Any]:
        try:
            run = ValidationHistory(
                id=f"val_{str(uuid.uuid4())[:8]}",
                schema_id=schema_id,
                result_status=status,
                issues_json=json.dumps(issues),
                duration_ms=duration_ms,
            )
            self.session.add(run)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "validation_run_logged", {"schema_id": schema_id, "status": status}
            )
            return {
                "id": run.id,
                "schema_id": run.schema_id,
                "result_status": run.result_status,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteExportRepository(ExportRepository):
    """SQLite implementation of Export history actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def log_export(
        self,
        export_id: str,
        job_id: str,
        format_name: str,
        file_path: str,
        checksum: str,
        file_size_bytes: int,
    ) -> dict[str, Any]:
        try:
            export = ExportHistory(
                id=export_id,
                job_id=job_id,
                format=format_name,
                file_path=file_path,
                checksum=checksum,
                file_size_bytes=file_size_bytes,
            )
            self.session.add(export)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "dataset_exported", {"job_id": job_id, "format": format_name}
            )
            return {
                "id": export.id,
                "job_id": export.job_id,
                "format": export.format,
                "file_path": export.file_path,
                "checksum": export.checksum,
                "file_size_bytes": export.file_size_bytes,
                "created_at": export.created_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def get_export(self, export_id: str) -> dict[str, Any] | None:
        try:
            export = self.session.execute(
                select(ExportHistory).where(ExportHistory.id == export_id)
            ).scalar_one_or_none()
            if not export:
                return None
            return {
                "id": export.id,
                "job_id": export.job_id,
                "format": export.format,
                "file_path": export.file_path,
                "checksum": export.checksum,
                "file_size_bytes": export.file_size_bytes,
                "created_at": export.created_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteDatasetMetadataRepository(DatasetMetadataRepository):
    """SQLite implementation of dataset metadata statistics persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def save_metadata(
        self,
        job_id: str,
        total_rows: int,
        table_stats: dict[str, Any],
        folder_path: str,
    ) -> dict[str, Any]:
        try:
            meta = DatasetMetadata(
                job_id=job_id,
                total_rows=total_rows,
                table_stats_json=json.dumps(table_stats),
                folder_path=folder_path,
            )
            self.session.add(meta)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "metadata_saved", {"job_id": job_id, "total_rows": total_rows}
            )
            return {
                "job_id": meta.job_id,
                "total_rows": meta.total_rows,
                "table_stats": table_stats,
                "folder_path": meta.folder_path,
                "created_at": meta.created_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def get_metadata(self, job_id: str) -> dict[str, Any] | None:
        try:
            meta = self.session.execute(
                select(DatasetMetadata).where(DatasetMetadata.job_id == job_id)
            ).scalar_one_or_none()
            if not meta:
                return None
            return {
                "job_id": meta.job_id,
                "total_rows": meta.total_rows,
                "table_stats": json.loads(meta.table_stats_json),
                "folder_path": meta.folder_path,
                "created_at": meta.created_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteIssueRepository(IssueRepository):
    """SQLite implementation for Caretaker Issue ticket actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def log_caretaker_issue(
        self,
        issue_id: str,
        category: str,
        severity: str,
        source: str,
        affected_component: str,
        suggested_fix: str,
    ) -> dict[str, Any]:
        try:
            issue = Issue(
                id=issue_id,
                category=category,
                severity=severity,
                source=source,
                status="open",
                affected_component=affected_component,
                suggested_fix=suggested_fix,
            )
            self.session.add(issue)

            evt = IssueEvent(
                id=f"evt_{issue_id}_created",
                issue_id=issue_id,
                event_type="Created",
                new_value="open",
                author="caretaker_daemon",
                notes="Initial monitoring sweep failure ticket created.",
            )
            self.session.add(evt)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "caretaker_issue_raised", {"issue_id": issue_id}
            )
            return {
                "id": issue.id,
                "category": issue.category,
                "severity": issue.severity,
                "status": issue.status,
                "detected_at": issue.detected_at,
            }
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def resolve_caretaker_issue(
        self, issue_id: str, resolution_notes: str
    ) -> None:
        try:
            issue = self.session.execute(
                select(Issue).where(Issue.id == issue_id)
            ).scalar_one()
            old_status = issue.status
            issue.status = "resolved"
            issue.resolved_at = datetime.datetime.utcnow()

            evt = IssueEvent(
                id=f"evt_{issue_id}_resolved_{int(datetime.datetime.utcnow().timestamp())}",
                issue_id=issue_id,
                event_type="StatusTransition",
                previous_value=old_status,
                new_value="resolved",
                author="caretaker_daemon",
                notes=resolution_notes,
            )
            self.session.add(evt)
            self.session.flush()
            DomainEventDispatcher.dispatch(
                "caretaker_issue_resolved", {"issue_id": issue_id}
            )
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteAuditRepository(AuditRepository):
    """SQLite implementation of operations audit trails."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def log_audit_event(
        self, event_type: str, action: str, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            details_dict = details or {}
            details_dict["action"] = action

            entry = AuditLog(
                id=str(uuid.uuid4()),
                event_type=event_type,
                component="MigrationEngine",
                actor="System",
                details_json=json.dumps(details_dict),
                occurred_at=datetime.datetime.utcnow(),
            )
            self.session.add(entry)
            self.session.flush()
            return {
                "id": entry.id,
                "event_type": entry.event_type,
                "component": entry.component,
                "actor": entry.actor,
                "details": details_dict,
                "occurred_at": entry.occurred_at.isoformat(),
            }
        except Exception as e:
            raise map_persistence_exception(e) from e


class SQLiteUnitOfWork(UnitOfWork):
    """SQLite implementation of the UnitOfWork pattern managing database sessions and logs."""

    def __init__(self) -> None:
        self.session: Session | None = None

    async def __aenter__(self) -> "SQLiteUnitOfWork":
        logger.info(EventID.LOG_INFO, "UnitOfWork transaction started.")
        if not sqlite_db_manager._session_factory:
            raise PersistenceError("Database manager has not been initialized.")
        self.session = sqlite_db_manager._session_factory()
        self._projects = SQLiteProjectRepository(self.session)
        self._schemas = SQLiteSchemaRepository(self.session)
        self._settings = SQLiteSettingsRepository(self.session)
        self._jobs = SQLiteJobRepository(self.session)
        self._validations = SQLiteValidationRepository(self.session)
        self._exports = SQLiteExportRepository(self.session)
        self._metadata = SQLiteDatasetMetadataRepository(self.session)
        self._issues = SQLiteIssueRepository(self.session)
        self._audits = SQLiteAuditRepository(self.session)
        return self

    @property
    def projects(self) -> ProjectRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._projects

    @property
    def schemas(self) -> SchemaRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._schemas

    @property
    def jobs(self) -> JobRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._jobs

    @property
    def validations(self) -> ValidationRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._validations

    @property
    def exports(self) -> ExportRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._exports

    @property
    def metadata(self) -> DatasetMetadataRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._metadata

    @property
    def settings(self) -> SettingsRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._settings

    @property
    def issues(self) -> IssueRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._issues

    @property
    def audits(self) -> AuditRepository:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        return self._audits

    async def commit(self) -> None:
        if not self.session:
            raise PersistenceError("No active session transaction.")
        try:
            logger.info(EventID.LOG_INFO, "UnitOfWork transaction commit triggered.")
            self.session.commit()
        except Exception as e:
            raise map_persistence_exception(e) from e

    async def rollback(self) -> None:
        if self.session:
            try:
                logger.info(
                    EventID.LOG_INFO, "UnitOfWork transaction rollback triggered."
                )
                self.session.rollback()
            except Exception as e:
                logger.error(
                    EventID.LOG_ERROR,
                    "UnitOfWork rollback failed — session may be in an inconsistent state.",
                    error=str(e),
                )

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.session:
            try:
                if exc_type:
                    await self.rollback()
            finally:
                self.session.close()
                self.session = None
                logger.info(EventID.LOG_INFO, "UnitOfWork transaction closed.")


class SQLitePersistenceProvider(PersistenceProvider):
    """SQLite-backed implementation coordinating repositories and UOW boundaries."""

    def unit_of_work(self) -> UnitOfWork:
        return SQLiteUnitOfWork()

    async def create_project(
        self,
        project_id: str,
        name: str,
        description: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.projects.create_project(
                project_id, name, description, status
            )
            await uow.commit()
            return res

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        async with self.unit_of_work() as uow:
            return await uow.projects.get_project(project_id)

    async def list_projects(self) -> list[dict[str, Any]]:
        async with self.unit_of_work() as uow:
            return await uow.projects.list_projects()

    async def save_schema(
        self, project_id: str, version: int, tables: list[Any], relationships: list[Any]
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.schemas.save_schema(
                project_id, version, tables, relationships
            )
            await uow.commit()
            return res

    async def get_active_schema(self, project_id: str) -> dict[str, Any] | None:
        async with self.unit_of_work() as uow:
            return await uow.schemas.get_active_schema(project_id)

    async def deactivate_schema(self, project_id: str) -> None:
        async with self.unit_of_work() as uow:
            await uow.schemas.deactivate_schema(project_id)
            await uow.commit()

    async def create_job(
        self, job_id: str, project_id: str, job_type: str, status: str
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.jobs.create_job(job_id, project_id, job_type, status)
            await uow.commit()
            return res

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        async with self.unit_of_work() as uow:
            return await uow.jobs.get_job(job_id)

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
        async with self.unit_of_work() as uow:
            await uow.jobs.update_job_status(
                job_id,
                status,
                progress,
                duration,
                result_summary,
                error_message,
                details,
            )
            await uow.commit()

    async def list_jobs(
        self, project_id: str | None = None
    ) -> Sequence[dict[str, Any]]:
        async with self.unit_of_work() as uow:
            return await uow.jobs.list_jobs(project_id)

    async def log_validation_run(
        self, schema_id: str, status: str, issues: list[Any], duration_ms: float
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.validations.log_validation_run(
                schema_id, status, issues, duration_ms
            )
            await uow.commit()
            return res

    async def log_export(
        self,
        export_id: str,
        job_id: str,
        format_name: str,
        file_path: str,
        checksum: str,
        file_size_bytes: int,
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.exports.log_export(
                export_id, job_id, format_name, file_path, checksum, file_size_bytes
            )
            await uow.commit()
            return res

    async def get_export(self, export_id: str) -> dict[str, Any] | None:
        async with self.unit_of_work() as uow:
            return await uow.exports.get_export(export_id)

    async def save_metadata(
        self,
        job_id: str,
        total_rows: int,
        table_stats: dict[str, Any],
        folder_path: str,
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.metadata.save_metadata(
                job_id, total_rows, table_stats, folder_path
            )
            await uow.commit()
            return res

    async def get_metadata(self, job_id: str) -> dict[str, Any] | None:
        async with self.unit_of_work() as uow:
            return await uow.metadata.get_metadata(job_id)

    async def set_app_setting(self, key: str, value: str) -> None:
        async with self.unit_of_work() as uow:
            await uow.settings.set_app_setting(key, value)
            await uow.commit()

    async def get_app_setting(self, key: str) -> str | None:
        async with self.unit_of_work() as uow:
            return await uow.settings.get_app_setting(key)

    async def log_caretaker_issue(
        self,
        issue_id: str,
        category: str,
        severity: str,
        source: str,
        affected_component: str,
        suggested_fix: str,
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.issues.log_caretaker_issue(
                issue_id, category, severity, source, affected_component, suggested_fix
            )
            await uow.commit()
            return res

    async def resolve_caretaker_issue(
        self, issue_id: str, resolution_notes: str
    ) -> None:
        async with self.unit_of_work() as uow:
            await uow.issues.resolve_caretaker_issue(issue_id, resolution_notes)
            await uow.commit()

    async def log_audit_event(
        self, event_type: str, action: str, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with self.unit_of_work() as uow:
            res = await uow.audits.log_audit_event(event_type, action, details)
            await uow.commit()
            return res
