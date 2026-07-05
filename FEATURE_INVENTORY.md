# SafeSeedOps Lite — Feature Inventory

This document catalogues all features frozen under the SafeSeedOps Lite v1.0.0-rc1 release.

## 1. Project Dashboard
*   **Health Status Diagnostic Card:** Visualizes system status (Offline, Degraded, Healthy) and detail diagnostics (fastapi, python, redis, persistence status).
*   **Telemetry Events Log:** Direct visualization of recent background process signals.

## 2. Schema Designer
*   **Table and Column Builder:** Intuitive interface to create, modify, and delete schemas.
*   **Foreign Key Relationship Manager:** Explicitly declare relationships.

## 3. PostgreSQL DDL Import
*   **DDL Lexer & Parser:** Direct parse of raw PostgreSQL `CREATE TABLE` scripts to map schemas.

## 4. Interactive ER Diagram
*   **Visual ER Diagram View:** Responsive, visually structured representations of table relations.

## 5. Schema Validation Engine
*   **Topological Sorter:** Resolves sequence of creation, catching loops or validation errors (e.g. missing primary keys).

## 6. Data Generation Subsystem
*   **Batch Synthesis Engine:** Orchestrates relational data creation respecting foreign constraints.

## 7. Data Preview and Export Pipeline
*   **Data Preview Table:** Structured grid views to preview generated mock rows.
*   **Multi-format Exporters:** Download schema results in SQL, JSON, or CSV.

## 8. One-Command Developer Startup
*   **Pre-flight Checks:** Environment validation engine checking Python requirements and port availability.
