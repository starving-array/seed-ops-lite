# Technical Debt Inventory

This document tracks technical debt itemizations identified during the v3.0.0 audits.

---

## 1. Identified Code Duplication & Complexity
- **DB Operations in HITL**: Database queries in `intervention.py` and `notifications.py` open raw sqlite connections individually.
  - *Recommendation*: Refactor to leverage a shared platform repository helper.

---

## 2. Dependency Audit & Upgrades
- External dependencies are pinned in `pyproject.toml`. Pinned versions must be audited periodically for patch version updates.

---

## 3. Database Indexes
- To optimize scale, add indexes on the `approval_id` column within `workflow_notifications` and `workflow_interventions`.
