# SafeSeedOps Platform Baseline
**Stable Release Specifications & Verification Diagnostics**

---

## 1. System Architecture

SafeSeedOps Lite has transitioned from transient memory (Redis keys) to a relational database file (SQLite) as the source of truth for business data.

```text
┌────────────────────────────────────────────────────────┐
│                     Business Layer                     │
│    (FastAPI API routers, CLI commands, Seed engine)    │
└───────────────────────────┬────────────────────────────┘
                            │ (Uses Platform Interfaces)
                            ▼
┌────────────────────────────────────────────────────────┐
│                     Platform Layer                     │
│           (app.platform.persistence.resolver)          │
│          (app.platform.persistence.interfaces)         │
└───────────────────────────┬────────────────────────────┘
                            │ (Resolved DI Implementations)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Persistence Layer                    │
│      (app.platform.providers.sqlite.SQLiteUOW)         │
│     (app.platform.providers.sqlite.repositories)        │
└───────────────────────────┬────────────────────────────┘
                            │ (Executes Queries via ORM)
                            ▼
┌──────────────────────────────────────┐  ┌──────────────┐
│            SQLite Engine             │  │    Redis     │
│       (Permanent Business Data)       │  │ (Live State) │
└──────────────────────────────────────┘  └──────────────┘
```

---

## 2. Unit of Work & Repositories

Database actions are strictly segregated into domain repositories, wrapped by the atomic Unit of Work controller:
*   **`SQLiteUnitOfWork`**: Orchestrates transaction lifecycles, checkout sessions, and guarantees automatic rollback on exceptions.
*   **Independent Repositories**:
    *   `SQLiteProjectRepository`: Workspace records CRUD namespace.
    *   `SQLiteSchemaRepository`: Active database structure configurations.
    *   `SQLiteSettingsRepository`: Global configurations.
    *   `SQLiteJobRepository`: Status tracking for validation runs.
    *   `SQLiteValidationRepository`: Audit logs of validation runs.
    *   `SQLiteExportRepository`: History records of generated files.
    *   `SQLiteDatasetMetadataRepository`: Metrics for output datasets.
    *   `SQLiteIssueRepository`: Caretaker ticket lifecycle logs.
    *   `SQLiteAuditRepository`: Platform logs.

---

## 3. Domain Event Dispatcher

A lightweight dispatcher provides decoupled notifications when updates are processed in repositories:
*   `DomainEventDispatcher.register(callback)`: Subscribes listeners.
*   `DomainEventDispatcher.dispatch(event_name, payload)`: Emits updates to all registered channels and log lines.

---

## 4. Transaction Lifecycle

Every session boundary follows a strict context checkout cycle:

```text
[UOW Instantiated] ──> [__aenter__] ──> Session Checked Out
                                                │
                                                ▼
                                    [Repository Queries Run]
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          ▼ Success                                   ▼ Failure
                     [uow.commit()]                              [__aexit__]
                          │                                           │
                          ▼                                           ▼
                    [__aexit__] ──> Close Session               [uow.rollback()]
                                                                [__aexit__] ──> Close
```

---

## 5. Current System Limitations & Scope boundaries
*   **Scale scope**: Designed for single-tenant developer contexts.
*   **Write locks**: SQLite file locks limit high-volume concurrent writes. Concurrency is mitigated using optimistic locking checks.
*   **Redis caches**: Redis remains the active store for queues and execution progress metrics.

---

## 6. Next Implementation Phase (Phase 2.3)

In Phase 2.3, the system will implement:
*   The Caretaker Daemon for background health and index validation.
*   Periodic database pruning to keep the database footprint small.
*   Automatic schema verification checks on startup.
