# SafeSeedOps Platform Persistence Guidelines
**Architecture, Transacting, Concurrency, and Exception Handling**

---

## 1. Unit of Work (UOW) Pattern

The Unit of Work pattern coordinates database transactions and handles operations on multiple repositories atomically.

### Guidelines:
*   **Transaction Boundaries**: Repositories must **never** commit or rollback transactions themselves. Only the Unit of Work manages `commit()`, `rollback()`, and session scopes.
*   **Usage**: Access repositories through the UOW context manager:
    ```python
    async with provider.unit_of_work() as uow:
        # 1. Read / Write operations
        project = await uow.projects.get_project("proj_1")
        
        # 2. Complete transaction
        await uow.commit()
    ```

---

## 2. Repository Pattern

Each entity is governed by a dedicated repository, separating business logic from raw SQLAlchemy ORM entities:
*   `ProjectRepository`: Handles workspace workspace CRUD operations.
*   `SchemaRepository`: Manages schema design version records.
*   `SettingsRepository`: Global config lookups.
*   `JobRepository`: Manages task statuses and states.
*   `AuditRepository`: Operations logging.

---

## 3. Transaction Lifecycle

```text
[Get UOW Instance]
        │
        ▼
   [__aenter__] ──> Check out SQLAlchemy Session
        │
        ▼
   [Repository Actions] ──> Read/Write using session (No Commit)
        │
        ├─────────────────────────────┐
        ▼ Success                     ▼ Exception / Error
   [uow.commit()]                 [uow.rollback()]
        │                             │
        └──────────────┬──────────────┘
                       ▼
                  [__aexit__] ──> Close & release session
```

---

## 4. Centralized Exception Hierarchy

All raw database driver or SQLAlchemy exceptions are intercepted and mapped to platform exceptions before reaching endpoints or CLI runners:
*   `PersistenceError`: Base operations failure.
*   `DatabaseLockedError`: SQLite database file lock conflicts.
*   `EntityNotFoundError`: Requested database key or index resource missing.
*   `ConcurrencyError`: Optimistic locking conflict during saves.
*   `ValidationError`: Database constraint check failures (e.g. foreign keys).

---

## 5. Concurrency Strategy (Optimistic Locking)

SafeSeedOps Lite uses optimistic locking to prevent concurrent overwrite failures:
1.  **Version column**: `projects` table maintains a `version` column.
2.  **Conflict detection**: During updates, the update SQL statement queries matching version counters:
    ```sql
    UPDATE projects SET name = :name, version = version + 1 WHERE id = :id AND version = :current_version;
    ```
3.  **Assertion**: If zero rows are updated, a concurrent save has modified the entity. A `ConcurrencyError` is raised.
