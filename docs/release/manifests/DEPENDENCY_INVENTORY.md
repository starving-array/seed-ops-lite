# SafeSeedOps Lite — Dependency Inventory

This document lists the third-party dependencies, libraries, and runtime platforms verified and pinned for SafeSeedOps Lite v1.0.0-rc1.

## 1. Python Environment Dependencies (`pyproject.toml`)
*   **Python:** `>=3.12` (compatible up to Python `3.13`)
*   **fastapi:** `>=0.111.0` (REST routing)
*   **uvicorn:** `>=0.30.1` (development server host)
*   **pydantic / pydantic-settings:** `>=2.7.4` / `>=2.3.3` (settings parsing)
*   **redis:** `>=5.0.6` (queues client)
*   **sqlalchemy / alembic:** `>=2.0.51` / `>=1.18.5` (database connections and migration runner)
*   **pyarrow:** `>=24.0.0` (data formatting)
*   **structlog:** `>=24.2.0` (structured logging)

## 2. Frontend JS/TS Dependencies (`frontend/package.json`)
*   **React:** `^19.2.7`
*   **React DOM:** `^19.2.7`
*   **React Router DOM:** `^7.18.0`
*   **Vite:** `^8.1.0` (build bundle compiler)
*   **TailwindCSS:** `^4.3.1` (styling engine)
*   **vitest:** `^4.1.9` (testing framework)
