# Security Guide

This guide details role authorization controls, workspace boundary isolation, and secret management mechanisms.

---

## 1. Role-Based Access Controls (RBAC)
The `InterventionEngine` checks user credentials and roles (`Operator`, `Admin`, `Engineer`) to prevent unauthorized pauses or restarts.

---

## 2. SQL Injection Mitigation
All database queries are executed using parameterized SQL placeholders (`?`) to prevent exploitation.

---

## 3. Log Sanitization
Structured logs prevent leakage of credentials, tokens, secrets, or reviewer comment inputs.
