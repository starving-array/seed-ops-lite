# SafeSeedOps Lite

SafeSeedOps Lite is an enterprise-grade synthetic relational database generator using a multi-agent architecture. This project provides the backend foundation, schema visualizer, and relational synthesis suites.

---

## Quick Start

### 1. Developer Environment Bootstrap
Install dependencies and initialize the workspace checklist:
```bash
# Setup dependencies and validation tools
uv sync

# Run diagnostics and pre-flight checks
uv run seed status
```

### 2. Launch Developer Mode
Run the FastAPI backend server:
```bash
uvicorn app.main:app --reload --port 8000
```
In a separate terminal, launch the frontend React SPA client:
```bash
cd frontend
npm install
npm run dev
```

---

## Key Features

*   **Interactive Schema Designer:** Build and configure schemas locally.
*   **PostgreSQL DDL Import:** Parse and convert SQL scripts into structured relational definitions.
*   **Cost-Aware Topological Planner:** Computes sequence validation gates and execution plans for database generation.
*   **Diagnostics Health Panel:** System pre-flight warnings and fallback checks.

---

## Project Structure

*   `app/`: FastAPI Backend routing, validation, planning, and generation services.
*   `frontend/`: React SPA user interface.
*   `tests/`: Verification suites and performance benchmark scripts.
*   `docs/`: Design documents and technical manuals.

---

## Testing & Quality Check

```bash
# Format verification
black app/ tests/

# Linter checks
ruff check app/ tests/

# Strict type checks
mypy app/

# Unit & integration tests
pytest
```

---

## Documentation Home

For complete guides, tutorials, design papers, and API specifications, visit the [Documentation Home](/docs/README.md).

*   [Developer Setup Runbook](/docs/features/DEVELOPER_STARTUP.md)
*   [Overall Architecture Index](/ARCHITECTURE_INDEX.md)
*   [SafeSeedOps Pro Roadmap & Deferred Backlogs](/docs/roadmap/ROADMAP_v3.1.md)
*   [General Availability Release Notes](/docs/release/ga/GA_RELEASE_REPORT.md)

---

## License

This project is licensed under the Apache License 2.0. See [LICENSE](/LICENSE) for details.
