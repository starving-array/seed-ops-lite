# SQLite Database Schema Specification
**SafeSeedOps Lite & Pro Persistence Engine Design**

---

## 1. Entity Relationship (ER) Diagram

```mermaid
erDiagram
    PROJECTS ||--o{ SCHEMAS : "cascade delete"
    PROJECTS ||--o{ JOBS : "cascade delete"
    SCHEMAS ||--o{ VALIDATION_HISTORY : "cascade delete"
    JOBS ||--|| EXPORT_HISTORY : "cascade delete"
    JOBS ||--|| DATASET_METADATA : "cascade delete"
    ISSUES ||--o{ ISSUE_EVENTS : "cascade delete"
    CARETAKER_HISTORY ||--o{ ISSUES : "tracks status"

    PROJECTS {
        text id PK
        text name
        datetime created_at
        datetime updated_at
    }

    SCHEMAS {
        text id PK
        text project_id FK
        integer version
        text tables_json
        text relationships_json
        integer is_active
        datetime created_at
    }

    JOBS {
        text id PK
        text project_id FK
        text type
        text status
        real progress
        datetime started_at
        datetime finished_at
        real duration
        text result_summary
        text error_message
        text details_json
    }

    VALIDATION_HISTORY {
        text id PK
        text schema_id FK
        datetime run_at
        text result_status
        text issues_json
        real duration_ms
    }

    EXPORT_HISTORY {
        text id PK
        text job_id FK
        text format
        text file_path
        text checksum
        integer file_size_bytes
        datetime created_at
    }

    DATASET_METADATA {
        text job_id PK FK
        integer total_rows
        text table_stats_json
        text folder_path
        datetime created_at
    }

    ISSUES {
        text id PK
        text category
        text severity
        text status
        datetime detected_at
        datetime resolved_at
        text source
        text affected_component
        text suggested_fix
    }

    ISSUE_EVENTS {
        text id PK
        text issue_id FK
        text event_type
        text previous_value
        text new_value
        datetime occurred_at
        text author
        text notes
    }

    CARETAKER_HISTORY {
        text id PK
        datetime run_at
        text checked_modules_json
        integer unhealthy_count
        integer actions_taken
    }

    APP_SETTINGS {
        text key PK
        text value
        datetime updated_at
    }
```

---

## 2. Table Schemas & Column Specifications

### 2.1 Table: `projects`
Stores high-level workspace project parameters.
*   `id` (TEXT, PK): Unique project identifier.
*   `name` (TEXT): Human-readable name of the project.
*   `created_at` (DATETIME): Timestamp of record insertion.
*   `updated_at` (DATETIME): Timestamp of last details update.

### 2.2 Table: `schemas`
Retains the revision history of relational database entity definitions.
*   `id` (TEXT, PK): Unique schema version identifier.
*   `project_id` (TEXT, FK references `projects.id` ON DELETE CASCADE): The associated project.
*   `version` (INTEGER): Auto-incrementing version revision count.
*   `tables_json` (TEXT): Compressed JSON dump of tables and column types.
*   `relationships_json` (TEXT): Compressed JSON dump of foreign keys and cascade rules.
*   `is_active` (INTEGER): Boolean flag (`1` for active designer state, else `0`).
*   `created_at` (DATETIME): Timestamp of saving.

### 2.3 Table: `jobs`
Maintains execution logs and metrics for generation and export runs.
*   `id` (TEXT, PK): Unique task execution session ID (e.g. `workflowId`).
*   `project_id` (TEXT, FK references `projects.id` ON DELETE CASCADE): The project triggering this run.
*   `type` (TEXT): Run type (`'generation' | 'export'`).
*   `status` (TEXT): Job state (`'Queued' | 'Running' | 'Completed' | 'Failed' | 'Cancelled'`).
*   `progress` (REAL): Float representation of progress percent (`0.00` to `100.00`).
*   `started_at` (DATETIME): Timestamp of execution start.
*   `finished_at` (DATETIME, Nullable): Timestamp of execution completion.
*   `duration` (REAL): Task duration in seconds.
*   `result_summary` (TEXT, Nullable): Completion status message.
*   `error_message` (TEXT, Nullable): Full traceback details on failures.
*   `details_json` (TEXT, Nullable): Table progress map and statistics JSON dump.

### 2.4 Table: `validation_history`
Audit records of local compiler and LLM agent checks.
*   `id` (TEXT, PK): Unique run identifier.
*   `schema_id` (TEXT, FK references `schemas.id` ON DELETE CASCADE): Evaluated schema.
*   `run_at` (DATETIME): Timestamp of execution.
*   `result_status` (TEXT): Compilation result (`'passed' | 'warning' | 'failed'`).
*   `issues_json` (TEXT): Array of structural/naming violation models.
*   `duration_ms` (REAL): Validation run duration in milliseconds.

### 2.5 Table: `export_history`
Logs file-package deliveries.
*   `id` (TEXT, PK): Unique export identifier.
*   `job_id` (TEXT, FK references `jobs.id` ON DELETE CASCADE): The generation task feeding this export.
*   `format` (TEXT): Target format extension (`'csv' | 'json' | 'sql'`).
*   `file_path` (TEXT): Location of the generated zip/dataset file.
*   `checksum` (TEXT): SHA-256 file contents verification hash.
*   `file_size_bytes` (INTEGER): Total footprint size on disk.
*   `created_at` (DATETIME): Timestamp.

### 2.6 Table: `dataset_metadata`
Stores the indices of local Parquet datasets.
*   `job_id` (TEXT, PK, FK references `jobs.id` ON DELETE CASCADE): Session ID.
*   `total_rows` (INTEGER): Cumulative records count.
*   `table_stats_json` (TEXT): Mapping of table names to row count and Parquet file path checksums.
*   `folder_path` (TEXT): Absolute path to the datasets directory on disk.
*   `created_at` (DATETIME): Timestamp.

### 2.7 Table: `issues`
Core tickets logged by the Caretaker agent.
*   `id` (TEXT, PK): Unique issue tracker ticket code.
*   `category` (TEXT): Category code (`'Storage' | 'Memory' | 'Security' | 'JobLifecycle'`).
*   `severity` (TEXT): Severity levels (`'info' | 'warning' | 'error' | 'critical'`).
*   `status` (TEXT): Ticket state (`'open' | 'in_progress' | 'resolved' | 'ignored'`).
*   `detected_at` (DATETIME): Timestamp of failure observation.
*   `resolved_at` (DATETIME, Nullable): Timestamp of issue correction.
*   `source` (TEXT): Detector identifier (`'caretaker_daemon' | 'middleware'`).
*   `affected_component` (TEXT): Component context details.
*   `suggested_fix` (TEXT): Suggested commands/guide details.

### 2.8 Table: `issue_events`
Append-only logs tracking details of issue state changes.
*   `id` (TEXT, PK): Event identifier.
*   `issue_id` (TEXT, FK references `issues.id` ON DELETE CASCADE): Associated issue ticket.
*   `event_type` (TEXT): Action taken (`'Created' | 'SeverityChanged' | 'StatusTransition' | 'CommentAdded'`).
*   `previous_value` (TEXT, Nullable): State field value before update.
*   `new_value` (TEXT): State field value after update.
*   `occurred_at` (DATETIME): Timestamp.
*   `author` (TEXT): Process identifier or developer name.
*   `notes` (TEXT, Nullable): Custom explanation notes.

### 2.9 Table: `caretaker_history`
Chronicles of caretaker audit sweeps.
*   `id` (TEXT, PK): Sweep identifier.
*   `run_at` (DATETIME): Time of sweep start.
*   `checked_modules_json` (TEXT): Checked modules (e.g. database, disk, jobs, credentials).
*   `unhealthy_count` (INTEGER): Open failures found.
*   `actions_taken` (INTEGER): Automated prune/cancel events triggered.

### 2.10 Table: `app_settings`
Settings configurations datastore.
*   `key` (TEXT, PK): Unique configuration setting key.
*   `value` (TEXT): Value details.
*   `updated_at` (DATETIME): Timestamp of modification.

---

## 3. Indexes & Constraints

To optimize search and listing query speeds, the following indexes are declared:
*   `idx_schemas_project_id`: ON `schemas(project_id)` -> Accelerates schema design canvas reads.
*   `idx_jobs_project_id_started`: ON `jobs(project_id, started_at DESC)` -> Speeds up job history feeds.
*   `idx_validation_schema_id`: ON `validation_history(schema_id)` -> Quick access to historical checks.
*   `idx_issue_events_issue_id`: ON `issue_events(issue_id, occurred_at ASC)` -> Speeds up issue history trace reconstructions.
*   `idx_issues_status_severity`: ON `issues(status, severity)` -> Optimizes caretaker monitoring sweeps.

---

## 4. The Append-Only Issue Event Model

### 4.1 Design Philosophy
Rather than updating the status or severity of an issue ticket directly on the issue row (e.g. `UPDATE issues SET status = 'resolved'`), the system introduces the `issue_events` model to record changes sequentially.

```text
                  [Issue: issue_011 (Status: Resolved)]
                                   │
                                   ▼
    [Issue Events Timeline (Reconstructed from idx_issue_events_issue_id)]
┌──────────────────────────┬──────────────────────────┬──────────────────────────┐
│   Event: 'Created'       │  Event: 'StatusChange'   │  Event: 'StatusChange'   │
│   Occurred: 10:00:00     │  Occurred: 10:05:00     │  Occurred: 10:08:00     │
│   Val: status=open       │  Val: status=in_progress │  Val: status=resolved    │
│   Author: Caretaker      │  Author: Dev-Jane        │  Author: Caretaker       │
└──────────────────────────┴──────────────────────────┴──────────────────────────┘
```

### 4.2 Rationale & Advantages
1.  **Immutability and Audit Trails**: Provides an audit log of how issues were resolved. Essential for compliance in high-security configurations.
2.  **No Loss of Context**: Prevents loss of comments, assignee reallocations, and chronological history when updating ticket parameters.
3.  **Timeline Analytics**: Enables measuring metrics like Mean Time to Resolution (MTTR) and tracing when issues are reopened.
4.  **Database Concurrency**: Reduces lock contentions by making write operations append-only.

---

## 5. Retention & Migration Strategy

### 5.1 Data Lifecycle Management
*   **Disk Cleanup Trigger**: When `Caretaker` sweeps `dataset_metadata`, it queries records where `created_at` is older than `24 hours`. It deletes the target local folder and prunes files, then cleans up database logs.
*   **Database Compaction**: An automatic SQL sweep executes a `VACUUM` call every 7 days (or during low usage hours) to optimize space.

### 5.2 Database Migration using Alembic
1.  **Initialization**: Define base models inside `app/platform/persistence/models.py`.
2.  **Alembic Setup**: Initialize configuration pointing to the local `storage/database.sqlite` file.
3.  **Auto-generation**: Generate script models (`alembic revision --autogenerate -m "Add base platform tables"`).
4.  **Transaction Control**: SQLite lacks fully transactional DDL modifications. Migrations use batch table copies to prevent schema corruption.
5.  **Downgrade Testing**: Every migration script must be tested for downgrades to ensure safety.

---

## 6. Future Compatibility (PostgreSQL/Oracle/MySQL)
All column data types leverage standard SQLite types (`TEXT`, `INTEGER`, `REAL`, `DATETIME`) which map cleanly to:
*   `VARCHAR` / `TEXT` / `JSON` in PostgreSQL.
*   `INT` / `DATETIME` / `DECIMAL` in MySQL.
*   `VARCHAR2` / `NUMBER` / `TIMESTAMP` in Oracle.
No database-specific constructs are used, ensuring the schema remains database-agnostic.

---

## 7. System Metadata & Audit Logs Specification

### 7.1 Table: `system_metadata`
Stores application-wide persistence versions to coordinate automated schema updates and cross-edition upgrades.
*   `id` (TEXT, PK): Unique config row key.
*   `platform_version` (TEXT): The runtime platform release code.
*   `schema_version` (INTEGER): The incremental version of the SQLite schema format.
*   `storage_version` (INTEGER): The version of the file dataset directory structure.
*   `migration_version` (TEXT): The active revision code matching Alembic migrations.
*   `created_at` (DATETIME): Time of initialization.
*   `updated_at` (DATETIME): Time of last version update.

#### Upgrade Strategy & Compatibility:
1.  **Bootstrap**: During application startup, if the database is empty, the bootstrapper creates tables and inserts an initial record with version counts.
2.  **Version Validation**: The bootstrapper compares `platform_settings.PERSISTENCE_VERSION` against the database's `schema_version`.
3.  **Migration Execution**: If the code version is higher, it executes the target Alembic migration scripts. If the database version is higher, it blocks startup, warning that a newer platform version is active on the file.

---

### 7.2 Table: `audit_logs`
An append-only database table logging key security, structural, and connection actions.
*   `id` (TEXT, PK): Unique log ID.
*   `event_type` (TEXT): Action type (e.g. `Project Created`, `Schema Saved`, `Schema Imported`, `Validation Started`, `Validation Passed`, `Generation Started`, `Generation Completed`, `Export Downloaded`, `Dataset Deleted`, `Redis Connected`, `Redis Disconnected`, `Caretaker Cleanup`).
*   `component` (TEXT): Target component name.
*   `actor` (TEXT): Performing user or automated daemon.
*   `details_json` (TEXT): Event payload context details.
*   `occurred_at` (DATETIME): Timestamp.

#### Retention Policy:
By default, the Caretaker daemon prunes audit logs older than **90 days** (configurable via `platform_settings.AUDIT_LOG_RETENTION_DAYS`) to prevent SQLite database growth.

---

## 8. Database Lifecycle & Flow Specifications

### 8.1 Initialization Flow
When the FastAPI application boots up, the lifespan hook executes `sqlite_db_manager.initialize()`:
1.  **Directory Verification**: Verifies the parent directory of `SQLITE_DB_PATH` exists, creating it recursively if missing.
2.  **Engine Creation**: Instantiates the SQLAlchemy Engine using WAL mode and setting connection timeouts.
3.  **PRAGMA Registration**: Registers listener triggers to enforce foreign key validations (`PRAGMA foreign_keys=ON`) and journal overrides.
4.  **Integrity Sweeps**: Executes `PRAGMA integrity_check` to verify database health. If malformed, raises a `DatabaseCorruptedException` immediately to halt startup.

```text
[FastAPI Start] ──> [Ensure Dir exists] ──> [Create Engine] ──> [Integrity Sweep] ──> [Apply Migrations]
```

### 8.2 Migration Workflow
SafeSeedOps Lite runs database schema upgrades programmatically on boot:
1.  **Alembic Ingestion**: Ingests configurations dynamically from `alembic.ini`.
2.  **Schema Comparison**: Queries the target database's `alembic_version` table.
3.  **Upgrade Execution**: Calls `alembic.command.upgrade()` to run any unapplied migration revisions up to `head`.

### 8.3 Connection & Session Lifecycle
*   **Connection Pool**: Managed by SQLAlchemy's connection pool with a pool size of 5 and max overflow of 10.
*   **Session Boundary**: Created per transaction thread using `sessionmaker(bind=engine)`.
*   **Graceful Shutdown**: Close connection handles dynamically by calling `sqlite_db_manager.shutdown()` when the lifespan shutdown hook fires.

### 8.4 Transaction Lifecycle
Every database read/write transaction runs inside the `sqlite_db_manager.session()` context manager to ensure atomicity:
1.  **Begin**: A session is checked out and a transaction begins.
2.  **Operation**: The query or update block executes.
3.  **Commit**: If successful, changes are automatically committed to the database.
4.  **Rollback**: If any exception is thrown, the transaction is immediately rolled back and SQLite connection holds are restored.
5.  **Close**: The session is guaranteed to close and release back to the pool.

---

## 9. Phase 2.2B Business Persistence Core Flows

### 9.1 Project Persistence Flow
*   **CRUD Operations**: Handled via `create_project()` and `get_project()`.
*   **Decoupled Context**: All operations map to the project resolved via `ProjectResolver.get_active_project_id()` to prepare for future multi-workspace models.

### 9.2 Schema Persistence Flow
*   **Version History**: Sequential version history is supported. When a new schema is saved via `save_schema()`, the version is incremented.
*   **Active Flag Rotation**: In a single transaction, the database manager deactivates previous versions of the project's schema (`UPDATE schemas SET is_active = 0 WHERE project_id = :project_id`) and writes the new schema version with `is_active = 1`.
*   **Auto-save Sync**: Auto-saves invoke `save_schema()` which appends a new active row history version, keeping full audit logs of structural transitions.

---

## 10. Repository Architecture, Unit of Work, & Concurrency

### 10.1 Unit of Work & Repositories
To support high scalability, `PersistenceProvider` resolves concrete instances of the `UnitOfWork` pattern:
*   **Unit of Work**: Manages SQLAlchemy session context boundaries and transaction control.
*   **Decoupled Repositories**: Individual classes (e.g. `SQLiteProjectRepository`, `SQLiteSchemaRepository`) coordinate queries without transacting.

### 10.2 Database Performance & Index Strategy
Indexes are configured in `sqlite_models.py` to optimize query lookups:
*   `idx_schema_project_active` (Composite: `project_id`, `is_active`): Accelerates fetching the latest active schema revision for a workspace.
*   `ix_schemas_project_id` & `ix_schemas_is_active` (Single): Optimizes lookup performance.
*   `ix_jobs_project_id` & `ix_validation_history_schema_id`: Speeds up joins and foreign key filters.
*   `ix_audit_logs_event_type`: Accelerates audit log history lookups.

### 10.3 Optimistic Concurrency Strategy
*   `Project.version`: Mapped integer column serving as a conflict detection counter.
*   **Conflict checks**: When performing updates, queries verify if the version is equal to `current_version`, incrementing on success or raising `ConcurrencyError` on mismatch.

### 10.4 Extended Health Status Diagnostics
The `/health` endpoint exposes database diagnostics inside `sqlite_status`:
*   `initialized`: boolean flag representing database pool startup status.
*   `migration_status`: active state check (`completed` or `pending`).
*   `pending_migrations`: array list of any unapplied Alembic revisions.
*   `last_successful_migration_at`: ISO timestamp of the last system upgrade.




