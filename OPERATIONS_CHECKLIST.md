# Operations Checklist (v3.0.0 GA)

This checklist outlines the procedures required for operational readiness.

## Daily Monitoring
- [x] Check logs for warnings or errors.
- [x] Check telemetry metrics for latency variations.

## Backups & Retention
- [x] Copy SQLite database files while WAL mode is active:
  ```bash
  cp safeseedops.db safeseedops_backup.db
  ```
- [x] Ensure 30-day notification retention cleanup runs regularly.
