# Rollback Plan (v3.0.0 GA)

This document contains step-by-step procedures for reverting the v3.0.0 release.

---

## 1. Rollback Trigger Criteria
A rollback is triggered if:
- Workflow engines experience write lockout blocks.
- Checkpoints fail verification checks.

---

## 2. Rollback Steps
1. Stop the application processes.
2. Restore database from the backup copy (`safeseedops_backup.db`).
3. Revert code release to the previous commit tag.
4. Restart application processes.
