# Deployment Checklist (v3.0.0 GA)

This checklist outlines the procedures required for production launch deployment.

## Pre-Deployment Verification
- [x] Run `uv run seed status` to verify quality gates.
- [x] Check that the latest Alembic schema is applied.

## Database Initialization
- [x] Upgrade SQLite schemas to HEAD:
  ```bash
  uv run alembic upgrade head
  ```

## Health & Logging Checks
- [x] Ensure health check returns PASS status.
- [x] Set log level environment overrides using `LOG_LEVEL` variables.
