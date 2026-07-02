# Runtime Platform Specification
**High-Availability Caching, Queue Management, and Offline Failover**

---

## Storage & Persistence Roles

The system is configured under a strict storage hierarchy where SQLite acts as the single source of truth, and the Runtime Platform (RuntimeProvider) acts purely as a transient cache:

*   **SQLite (Single Source of Truth)**: Permanently stores Projects, Schemas, Jobs, Dataset Metadata, and Configuration. A Redis outage never affects schemas or job history.
*   **RuntimeProvider (Transient Cache)**: Manages temporary, disposable state (Queues, Progress metrics, Cancellation flags, and websocket sessions).
*   **DiskDatasetStorageManager (Parquet Storage)**: Stores generated synthetic datasets as Parquet files with `manifest.json`. Datasets never exist solely in memory.

---

## Runtime Responsibility Matrix

| Layer | Type | Stores | Survives Redis Outage? |
|---|---|---|---|
| **SQLite** | Durable | Projects, Schemas, Jobs, Job History, Dataset Metadata, Export Metadata, Runtime Config | ✅ Always |
| **DiskDatasetStorageManager** | Durable | Parquet files, manifest.json | ✅ Always |
| **RuntimeProvider (Redis/Memory)** | Transient Cache | Queues, Progress, Cancellation Flags, Heartbeats, Preview Cache, Export Payload Cache | ❌ Disposable |

**Critical rule:** If RuntimeProvider and SQLite disagree, SQLite is always correct. SQLite state must never be reconstructed from RuntimeProvider.

---

## 1. Runtime Architecture

The Runtime Platform manages transient system state (active workers, live jobs progress, task queues) using a delegated manager pattern:

```text
              Application
                   │
                   ▼
             RuntimeManager (DI Singleton)
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
RedisRuntimeProvider   MemoryRuntimeProvider
(Primary Active)       (Secondary Fallback)
```

---

## 2. Fallback Flow

If a connection to Redis throws database exceptions during operations:
1.  **Intercept Exception**: `RuntimeManager` catches `DatabaseConnectionError`.
2.  **Fallback Trigger**: The manager switches `mode` to `"memory"` and `active_provider` to `MemoryRuntimeProvider`.
3.  **Broadcast Event**: Publishes `RuntimeFallbackActivated` and `RuntimeProviderChanged` events.
4.  **Graceful Recovery Monitor**: Starts a background polling task to wait for Redis.
5.  **Operation Re-routing**: Immediately executes the failed action on the in-memory provider so the calling business module does not crash.

---

## 3. Recovery Flow

While in memory fallback mode, the manager polls Redis at `platform_settings.RUNTIME_RECONNECT_INTERVAL_SECONDS` intervals:
1.  **Heartbeat Poll**: Ping Redis host.
2.  **Pool Reset**: Re-establish Redis pool connection on success.
3.  **Promotion**: Update `mode` back to `"redis"` and `active_provider` to `RedisRuntimeProvider`.
4.  **State Restore**: Switch active cache and record reconnection times.
5.  **Broadcast Event**: Publishes `RuntimeRecovered` and `RuntimeProviderChanged` events.

**Important:** Recovery never reconstructs SQLite data from Redis. SQLite is always authoritative.

---

## 4. Dataset Storage Flow (Phase 2.4.3 Hardened)

Generated datasets are NEVER stored only in RuntimeProvider:

```text
Generation Worker
      │
      ▼
DiskDatasetStorageManager.write_table_dataset(workflow_id, table, records)
      │
      ├─► Parquet file  (storage/datasets/dataset_{id}/{table}.parquet)
      ├─► manifest.json (storage/datasets/dataset_{id}/manifest.json)
      └─► SQLite dataset metadata (via persistence.save_metadata())
```

Preview endpoint resolution order:
1. Check RuntimeProvider cache (`generation:{id}:records`)
2. If cache miss → load from `DiskDatasetStorageManager.read_table_dataset_preview()`
3. Optionally repopulate RuntimeProvider cache

Export endpoint resolution order:
1. Check RuntimeProvider cache (`generation:{id}:records`)
2. If cache miss → load from `DiskDatasetStorageManager` Parquet files

Export download endpoint resolution order:
1. Check RuntimeProvider cache (`export:{id}:payload`)
2. If cache miss → re-stream from `DiskDatasetStorageManager.stream_multi_table_zip()`

---

## 5. Runtime Events Catalog

Emitted through `DomainEventDispatcher`:
*   `RuntimeStarted`: Dispatched on initialization.
*   `RuntimeStopped`: Dispatched on shutdown.
*   `RedisConnected`: Dispatched when Redis pool connects.
*   `RedisDisconnected`: Dispatched when Redis pool disconnects.
*   `RuntimeFallbackActivated`: Dispatched when memory fallback activates.
*   `RuntimeRecovered`: Dispatched when primary Redis restores.
*   `RuntimeProviderChanged`: Dispatched when changing active engines.
*   `persistence_failure`: Dispatched when a SQLite write fails — never silent.

---

## 6. Configuration Settings

Configurable via `PlatformSettings` prefixing env vars with `PLATFORM_`:
*   `RUNTIME_REDIS_HOST` (string, default: `localhost`)
*   `RUNTIME_REDIS_PORT` (int, default: `6379`)
*   `RUNTIME_REDIS_PASSWORD` (string, default: `None`)
*   `RUNTIME_REDIS_TIMEOUT_SECONDS` (float, default: `5.0`)
*   `RUNTIME_REDIS_MAX_CONNECTIONS` (int, default: `10`)
*   `RUNTIME_RECONNECT_INTERVAL_SECONDS` (float, default: `5.0`)
*   `RUNTIME_HEALTH_POLL_INTERVAL_SECONDS` (float, default: `10.0`)
*   `RUNTIME_MEMORY_FALLBACK_ENABLED` (bool, default: `True`)

---

## 7. Phase 2.4.3 Hardening Changes

| Fix | Change |
|---|---|
| **Fix #1** | Schema CRUD endpoints confirmed SQLite-only (no RuntimeProvider dependency) |
| **Fix #2** | Export endpoint falls back to DiskDatasetStorageManager when RuntimeProvider cache is missing |
| **Fix #3** | SQLite is always authoritative; RuntimeProvider is cache only |
| **Fix #4** | Removed legacy `get_redis` alias from `deps.py`; removed `RedisType` alias from `helpers.py` |
| **Fix #5** | Removed `contextlib.suppress` from `UnitOfWork.rollback()` — failures now log and propagate |
| **Fix #6** | Runtime banner updated: correctly states only *live runtime features* are in Local Runtime Mode |
| **Fix #7** | Health endpoint: degraded (not unhealthy) when Redis offline; 503 only for SQLite failure |
| **Fix #8** | Single `RuntimeManager` singleton verified — no duplicate initialization |
| **Fix #9** | All platform providers registered as singletons in DI container |
| **Fix #10** | Documentation updated (this file, PLATFORM_BASELINE.md, PERSISTENCE_AND_RUNTIME_ARCHITECTURE.md) |
