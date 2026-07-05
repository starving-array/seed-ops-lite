# SafeSeedOps Lite — v1.0.0-rc1 Release Notes

SafeSeedOps Lite is a developer-focused, single-user database schema builder, parser, and relational synthesis suite. This release candidate establishes the frozen v1.0.0 features set.

## What's New in v1.0.0-rc1

*   **Interactive Schema Designer:** Visual interface to configure databases, define primary keys, and manage relationships.
*   **PostgreSQL DDL Import:** Fast lexical compiler supporting SQL script ingestion and table schema conversion.
*   **Interactive ER Diagram:** Dynamic relation model rendering to inspect relationships.
*   **Cost-Aware Topological Planner:** Computes sequence validation gates and topological execution strategies for generating relational tables.
*   **Status Diagnostics Panel:** Comprehensive pre-flight system warnings (Python requirements verification, port configuration, and storage fallbacks).
*   **UX/UI Accessibility Polish:** Consistent theme tokens, visible keyboard focus indicators, and screen reader-friendly layout parameters.
*   **SQLite Fallback Mode:** Seamless operations using SQLite-only persistence when Redis cluster nodes are offline.
