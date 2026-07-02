# SafeSeedOps Platform Baseline
**Stable Release Specifications & Verification Diagnostics**

---

## 1. Storage & Persistence Architecture

The system segregates storage responsibilities into three distinct architectural layers:

### SQLite (Single Source of Truth)
SQLite is the **only durable persistence layer**. A Redis outage will never cause persistent data to disappear.
Stores:
*   Projects
*   Schemas
*   Jobs (Historical & State)
*   Job History
*   Metadata
*   Dataset Metadata
*   Export Metadata
*   Runtime Configuration

### RuntimeProvider (Transient Runtime Cache)
RuntimeProvider (Redis or local in-memory fallback) stores only **transient runtime information**. Everything inside it is disposable.
Stores:
*   Queue messages
*   Cancellation flags
*   Heartbeats
*   Websocket state
*   Live progress / status cache
*   Temporary preview cache
*   Temporary export payload cache

### DiskDatasetStorageManager (Parquet Storage)
DiskDatasetStorageManager handles serialization and deserialization of generated datasets as Parquet files on disk. Generated datasets never exist only inside the RuntimeProvider.
Stores:
*   Generated Datasets (Parquet files)
*   Dataset manifest files (`manifest.json`)

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

## 3. Domain Event Dispatcher & Runtime Monitor

*   **Decoupled Events**: Emits repository status changes and runtime switching notifications (`RuntimeFallbackActivated`, `RuntimeRecovered`).
*   **High-Availability Runtime**: `RuntimeManager` proxies caching and queueing calls to a `RedisRuntimeProvider` or falls back dynamically to a local `MemoryRuntimeProvider` under connection failures.

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
                    [__aexit__] ──> Close Session     [uow.rollback()] ← logs error, propagates
                                                                [__aexit__] ──> Close
```

**Note:** Rollback failures are logged as structured errors and are never silently suppressed (Phase 2.4.3).

---

## 5. Current System Limitations & Scope boundaries
*   **Scale scope**: Designed for single-tenant developer contexts.
*   **Write locks**: SQLite file locks limit high-volume concurrent writes. Concurrency is mitigated using optimistic locking checks.
*   **Transient Storage**: Redis and in-memory caches serve transient execution queue payloads only.

---

## 6. Phase 2.4.3 — Persistence Architecture Hardening

**Phase 2.4.3 applied the following correctness fixes:**

| # | Fix | Status |
|---|---|---|
| 1 | Schema endpoints (POST/GET/PUT/DELETE) verified SQLite-only | ✅ Done |
| 2 | Export endpoint falls back to DiskDatasetStorageManager when RuntimeProvider cache is gone | ✅ Done |
| 3 | Export download endpoint re-streams from Parquet if RuntimeProvider cache has expired | ✅ Done |
| 4 | Removed `get_redis` alias from `deps.py`; removed `RedisType` alias from `helpers.py` | ✅ Done |
| 5 | `UnitOfWork.rollback()` no longer silently suppresses errors | ✅ Done |
| 6 | Runtime banner corrected: only live runtime features are in Local Runtime Mode | ✅ Done |
| 7 | Health rules: degraded when Redis offline, 503 only for SQLite failure | ✅ Done |
| 8 | Single `RuntimeManager` singleton — no duplicate initialization | ✅ Done |
| 9 | All platform providers registered as DI singletons | ✅ Done |
| 10 | Documentation updated (RUNTIME_PLATFORM, PLATFORM_BASELINE, PERSISTENCE_AND_RUNTIME_ARCHITECTURE) | ✅ Done |

---

## 7. Next Implementation Phase (Phase 2.5)

In Phase 2.5, the system will implement:
*   The Caretaker Daemon for background health checks and indexes validations.
*   Periodic database and local dataset pruning tasks to maintain resource limits.
