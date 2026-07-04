# Support Runbook (v3.0.0 GA)

This runbook helps support engineers diagnose and troubleshoot issues.

---

## 1. Diagnostics Flow
- Check logs:
  ```bash
  grep "EventID.LOG_WARNING" safeseedops.log
  ```
- Check database files.

---

## 2. Common Issues
- **Problem**: `OperationalError: no such table: workflow_notifications`
  - **Solution**: The database table needs to be initialized. Instantiate `NotificationManager()` or execute Alembic upgrades to create the tables.
