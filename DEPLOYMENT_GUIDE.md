# Deployment Guide

This guide covers deployment targets, database initialization, and migration guides.

---

## 1. Database Initialization
Migrations are managed via Alembic:
```bash
uv run alembic upgrade head
```

---

## 2. Resource Sizing & Storage recommendations
- **Disk Space**: Requires minimal persistent storage (approx. 50 MB for database growth).
- **RAM**: Capped under 15 MB for concurrent worker processing loops.
- **CPU**: Minimal CPU spikes. Average thread pools scale with target concurrency parameters.
