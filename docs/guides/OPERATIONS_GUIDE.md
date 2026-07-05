# SafeSeedOps Lite — Operations Guide

This guide documents installation, environment variables, health checks, and logging configurations.

## 1. Startup & Installation
To boot the platform:
```bash
uv pip install -r pyproject.toml
uv run seed status
```

## 2. Environment Variables & Logging
*   Default logging output: Structured JSON telemetry lines output to `sys.stdout`.
*   Level overrides can be passed via `LOG_LEVEL` environment variable.

## 3. Database Backup & Restore
*   The database is a single local SQLite file: `safeseedops.db`.
*   Backup can be created by copying the file safely while in WAL mode:
    ```bash
    cp safeseedops.db safeseedops_backup.db
    ```
