# Legacy Redis-to-SQLite Migration Specification
**SafeSeedOps Lite Idempotent Database Bootstrapper**

---

## 1. Migration & Verification Flow

To support transitioning from transient Redis-only storage to SQLite persistence, SafeSeedOps Lite runs an automated legacy datastore migration during application lifespan boot. The execution follows a strict verification cycle:

```text
[Lifespan Start]
       │
       ▼
[Ensure DB Backup] ──> [Fetch Redis Schema] ──> [Write SQLite Schema]
                                                        │
                                                        ▼
                                             [Read SQLite Schema Back]
                                                        │
                                                        ▼
                                             [Verify Structural Match]
                                                        │
                         ┌──────────────────────────────┴──────────────────────────────┐
                         ▼ Success                                                     ▼ Failure
             [Set status = "completed"]                                      [Restore Backup DB]
             [Log "migration_completed"]                                     [Log "migration_failed"]
             [Delete Backup File]                                            [Re-raise Error]
```

---

## 2. Idempotent Migration Design

*   **Completion Flag**: The database manager tracks execution status inside the `app_settings` table (key: `"redis_migration_status"`, value: `"completed"`).
*   **Safety Assertions**: Before running any insertions, the migration runner queries the flag. If it is `"completed"`, the block returns immediately and logs `migration_skipped`.
*   **Transient Handling**: If the Redis client goes offline or raises a timeout during the connection handshake, the migration runner skips execution. Because the flag remains un-written, the next system restart will attempt migration again, preventing partial/corrupt data conversions.
*   **Preservation Guarantee**: The migration reads data using Redis `get` queries. It **does NOT delete or flush** any keys from Redis, ensuring no legacy data is lost.

---

## 3. Database Backup & Safety Recovery Procedures

Before any database writes are attempted, a safety backup of the database file is made:
1.  **Backup creation**: Copies the active `database.sqlite` file to `database.sqlite.backup`.
2.  **Verification checks**: Validates that all migrated schemas match structural definitions.
3.  **Automatic restore on fail**: If any error or verification check fails:
    1. Close database engine pools (`sqlite_db_manager.shutdown()`).
    2. Overwrite the corrupted `database.sqlite` file with `database.sqlite.backup`.
    3. Re-initialize connection pools and Alembic mappings (`sqlite_db_manager.initialize()`).
    4. Delete the backup file.
    5. Re-raise the exception to halt startup or raise alerts.
4.  **Automatic clean up on success**: Deletes `database.sqlite.backup` file.

---

## 4. Centralized Project Resolver Pattern

To avoid hardcoded project values, the application uses the `ProjectResolver` to resolve the project's namespace.
*   **Location**: `app/platform/persistence/resolver.py`
*   **Interface**: `ProjectResolver.get_active_project_id()`
*   **Purpose**: Decouples literal `"default"` mappings from endpoints and managers, allowing seamless transition to multi-project models in future Pro editions.
