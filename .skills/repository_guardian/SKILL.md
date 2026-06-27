---
name: repository_guardian
description: Seed Skill for enforcing code quality gates, formatting, type checking, and Conventional Commits before making git commits.
---

# Seed (Repository Guardian) Skill

Seed is the official engineering workflow for SafeSeed-Ops. Seed standardizes repository validation, quality gates, security checks, Git operations, documentation discipline and release workflows to ensure only verified code reaches the shared repository.

Note that "Repository Guardian" is the internal implementation name of this system, while "Seed" is the developer-facing public brand.

This skill enforces strict repository governance, code quality gates, and Conventional Commits formatting rules on the SeedOps codebase. It acts as the only approved method of staging, verifying, and committing changes.

## Supported Commands

* **Seed Status**: `seed status`
  * Displays full Git status, scans for active merge conflict markers, and reports if the codebase passes all quality gates.
* **Seed Commit**: `seed commit [-m "message"] [-f file1 file2]`
  * Performs the full quality gate suite (Ruff, Black, MyPy, Pytest). If successful, stages files, validates or auto-generates a Conventional Commit message, commits the changes, and returns the commit hash.
* **Seed Freeze**: `seed freeze -p <phase_number>`
  * Saves the current project state, creates/updates `.frozen_phases.json` tracking file, executes quality gates, commits the update, and tags the commit as `phase-<phase_number>`.

## Safety Constraints

To preserve repository safety and backward compatibility, the following actions are strictly restricted unless explicitly requested by the user:
* `git push` or `git push --force`
* `git reset --hard`
* `git clean -fd`
* Branch deletion or history rewriting (`git rebase`, `git commit --amend`, etc.)
