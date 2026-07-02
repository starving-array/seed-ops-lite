# SafeSeedOps Platform Principles
**Architectural Constraints, Decoupling Standards, and Clean Code Boundaries**

This document establishes the fundamental engineering guidelines that govern the next-generation SafeSeedOps architecture. 

---

## 1. Core Principles

### Principle 1: Business Logic Never Depends on Infrastructure
Business and application modules (e.g. topological seeding planner, Gemini structural validation, data compilers) must remain agnostic to where and how data is stored. They interact exclusively with interfaces and must never import or call concrete SQLite, Redis, MySQL, or S3 client drivers directly.

### Principle 2: Every Infrastructure Service Exposes an Interface
Infrastructure boundaries (such as database engines, transient key-value caches, file storages, and task workers) must expose a clean abstract base interface (using Python's `abc.ABC` module). All clients import and interact with these base interface types.

### Principle 3: SQLite is the Lite Source of Truth
For the SafeSeedOps Lite distribution, the SQLite database is the ultimate authority on configurations, designer schemas, projects, issues, and histories. No active state is stored exclusively in cache layers.

### Principle 4: Redis is a Runtime Accelerator
Redis acts as a transient, high-speed accelerator for queuing tasks, caching session states, and polling progress counters. The application must degrade gracefully and continue running without data loss if Redis goes offline.

### Principle 5: Generated Datasets are Artifacts
Generated mock records are structured assets. They are stored as compressed Parquet files on disk rather than loaded into database tables or cache memory values, preventing database bloat.

### Principle 6: Artifacts Always Include Metadata and Checksums
All files or export packages managed by the platform carry a `metadata.json` describing properties, row counts, creation timestamps, and SHA-256 integrity checksums. This prevents corrupted downloads.

### Principle 7: All Platform Services Must Be Independently Testable
Interfaces must support mocking (e.g. using `unittest.mock` or concrete in-memory mock adapters). This allows business logic to be tested independently of live Redis or SQLite instances.

### Principle 8: Long-Running Services Report Health
Daemon processes, caretaker monitors, and worker queues must regularly write status details to the platform datastore so that system connectivity panels can track their operational status.

### Principle 9: No Infrastructure Implementation Should Leak into Business Modules
Driver quirks, connection pools, and database-specific exception types must be handled within the provider implementations. They should be caught and re-raised as clean platform exception classes.

### Principle 10: Future Providers Must Be Swappable
Changing a provider (e.g., migrating from SQLite to PostgreSQL, or local disk to Amazon S3) must require only updating configuration settings, without modifying application or business logic files.

---

## 2. Decoupling Graph

```text
+-----------------------------------------------------------+
|               Business / Application Layer                |
|       (Topological Seeding, AI Generator, Exporter)       |
+-----------------------------+-----------------------------+
                              |
                     Interacts exclusively with
                              |
+-----------------------------v-----------------------------+
|                 Platform Abstract Interfaces               |
|   (PersistenceProvider, RuntimeProvider, ArtifactProvider) |
+-----------------------------+-----------------------------+
                              |
                     Implemented cleanly by
                              |
+-----------------------------v-----------------------------+
|                Concrete Infrastructure Providers          |
|      (SQLiteProvider, RedisProvider, S3ArtifactProvider)   |
+-----------------------------------------------------------+
```
