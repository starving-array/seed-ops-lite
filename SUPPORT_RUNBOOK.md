# SafeSeedOps Lite — Support Runbook

This runbook helps support engineers diagnose and troubleshoot issues in the SafeSeedOps Lite v1.0.0 release.

## 1. Diagnostics Flow
*   Check logs:
    ```bash
    grep "EventID.LOG_WARNING" safeseedops.log
    ```
*   Verify the SQLite database files.

## 2. Common Issues
*   **Problem:** `OperationalError: no such table: workflow_notifications`
    *   **Solution:** The database table needs to be initialized. Execute Alembic upgrades to create the tables.
