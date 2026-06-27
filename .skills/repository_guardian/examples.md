# Seed (Repository Guardian) Skill: Examples

This document displays execution examples of the Seed scripts (internally implemented as the Repository Guardian).

## 1. Checking Repository Status and Health (Seed Status)

### Command
```bash
seed status
```

### Healthy Output
```
=== Seed: Status & Health Report ===
Repository Path: C:\Users\lovea\Documents\hackathon\safeseedops-lite
Status: Git repository detected.
Merge Conflicts: None detected.

--- Git Status Summary ---
On branch main
nothing to commit, working tree clean

--- Quality Gates Health Diagnostics ---
All quality checks passed successfully!
Health Status: HEALTHY (All checks: Ruff, Black, MyPy, and Pytest pass)
```

---

## 2. Commit Command (Seed Commit) (Quality Checks Passed)

### Command
```bash
seed commit -m "feat(governance): add license to workspace"
```

### Output
```
Running quality gates...
All quality checks passed successfully!
Commit created successfully!
Hash: e4a3c20202bb8efc636f4d54d588523efccb999a
```

---

## 3. Commit Command (Seed Commit) (Quality Checks Failed)

### Command
```bash
seed commit -m "feat(cli): broken commit example"
```

### Output
```
Running quality gates...
Quality checks failed!
Commit aborted due to quality check failures:
- Ruff lint checks failed.
STDOUT:
app/cli/cli.py:46:15: PLR0911 Too many return statements (7 > 6)
Found 1 error.
```

---

## 4. Phase Freezing (Seed Freeze)

### Command
```bash
seed freeze -p 10
```

### Output
```
Freezing phase '10'...
Updated .frozen_phases.json
Running quality gate verification...
All quality checks passed successfully!
Created commit: b36d934279ab8eef636f56d54d588523efccb9090
Successfully tagged commit as 'phase-10'
```
