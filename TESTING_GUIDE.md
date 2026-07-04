# Testing Guide

This guide documents the test suite categories, coverage, and how to execute validations.

---

## 1. Test Categories
- **Unit Tests**: Targets class-level isolated functions. (e.g. `tests/test_hitl_notifications.py`).
- **Integration Tests**: Validates cross-component adapter sync workflows. (e.g. `tests/test_system_integration.py`).
- **Benchmark & Load Tests**: Assures P50 write latencies remain within performance bounds under concurrency stress. (e.g. `tests/test_hitl_load.py`).
- **Chaos & Failure Injections**: Verifies checkpoint database recovery points. (e.g. `tests/test_hitl_chaos.py`).

---

## 2. Running Quality Gates
Execute standard checks:
```bash
uv run seed status
```
This performs ruff checks, black formatting compliance, mypy static audits, and executes the entire Pytest suite.
