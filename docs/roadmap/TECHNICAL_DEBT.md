# SafeSeedOps Lite — Technical Debt Inventory

This document tracks identified refactoring candidates and technical debt items for the SafeSeedOps Lite codebase.

## 1. Database Operations Code Duplication
* **Issue:** Several endpoints open SQLite connection states independently.
* **Refactoring:** Abstract connection pool contexts into a unified repository base pattern inside `app/services/`.

## 2. Dependency Audit & Upgrades
* **Issue:** Python dependencies pinned in `pyproject.toml` and npm packages in `package.json` require scheduling regular security audits and minor updates.
* **Refactoring:** Configure automated audit tools (e.g. Dependabot, safety) to track packages.

## 3. Database Indexes Optimization
* **Issue:** Heavy relational schema datasets can encounter slow join checks without proper indices.
* **Refactoring:** Create indices on foreign key reference IDs (e.g. `approval_id`, `project_id`) across state tables.

## 4. State Management Refinement
* **Issue:** Multi-step Schema designer triggers complex renders.
* **Refactoring:** Transition state components to React Context providers or lightweight zustand stores to isolate state changes.
