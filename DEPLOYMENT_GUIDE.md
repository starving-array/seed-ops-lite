# SafeSeedOps Lite — Deployment Guide

This guide covers deployment targets, database initialization, and migration instructions for SafeSeedOps Lite v1.0.0.

## 1. Database Initialization
Migrations are managed via Alembic:
```bash
uv run alembic upgrade head
```

## 2. Resource Sizing Recommendations
*   **Disk Space:** Requires minimal persistent storage (approx. 50 MB for database growth).
*   **RAM:** Capped under 15 MB for concurrent worker processing loops.
*   **CPU:** Minimal CPU spikes. Average thread pools scale with target concurrency parameters.

## 3. Production Deployment Checks
*   Ensure the `PLATFORM_DEV_PORT` is set correctly.
*   Run the environment pre-flight diagnostics check using `uv run seed status`.
