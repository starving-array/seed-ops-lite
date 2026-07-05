# SafeSeedOps Lite — Known Limitations

The following items record functional limits of the Lite v1 edition. These are deferred as features reserved for the Pro or Enterprise editions.

## Deferred Features & Limitations

1. **Storage and Database Drivers:**
   * **Lite v1:** Single local SQLite database setup for project state metadata.
   * **Pro/Enterprise:** Multi-tenant support for PostgreSQL, MySQL, and enterprise database drivers.

2. **Distributed Queue Scaling:**
   * **Lite v1:** In-memory queue fallback when Redis is offline. Single process limits.
   * **Pro/Enterprise:** High-availability distributed Celery/Redis cluster queuing with scale-out workers.

3. **Cloud Export Targets:**
   * **Lite v1:** Local folder exports (JSON, SQL, CSV).
   * **Pro/Enterprise:** Stream-buffered cloud target exports (Amazon S3, Google Cloud Storage, Snowflake pipelines).

4. **Multi-User Collaboration:**
   * **Lite v1:** Local developer workspace, single-tenant focus.
   * **Pro/Enterprise:** Role-Based Access Control (RBAC), multi-user workspaces, audit logs, and shared projects.
