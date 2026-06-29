# Seed (Repository Guardian) Skill

Seed is the official engineering workflow for SafeSeed-Ops. Seed standardizes repository validation, quality gates, security checks, Git operations, documentation discipline and release workflows to ensure only verified code reaches the shared repository.

Note that "Repository Guardian" is the internal implementation name of this system, while "Seed" is the developer-facing public brand.

The Seed Skill enforces code quality checks and metadata tracking as a commit gate. Before any commit is executed, the repository status, merge conflicts, Ruff linting, Black formatting, MyPy static types, and Pytest test cases are executed. Commits are blocked if any check fails.

## Directory Structure

```
.skills/repository_guardian/
├── SKILL.md            # Skill frontmatter and triggers description
├── config.yaml         # Configuration mappings
├── README.md           # This documentation file
├── examples.md         # Example usages and outputs
└── scripts/
    ├── git_helpers.py       # Git subprocess execution helpers
    ├── quality_check.py     # Quality gate verification runner
    ├── commit.py            # Pre-commit gate runner
    ├── freeze_phase.py      # Phase freezing utility
    └── repository_status.py # Git and health reporter
```

## Requirements

* Python 3.12+
* Git command line utility
* Local virtual environment `.venv/` containing `ruff`, `black`, `mypy`, and `pytest`.

## Usage

### 1. Check Status & Health
Check if the codebase is healthy and view the Git status using Seed Status:
```bash
seed status
```

### 2. Verify and Commit Changes
Verify all quality gates, stage changes, and commit them using Seed Commit:
* With auto-generated Conventional Commit message:
  ```bash
  seed commit
  ```
* With custom Conventional Commit message:
  ```bash
  seed commit -m "feat(cli): add file existence checks"
  ```
* Commit specific files:
  ```bash
  seed commit -f app/cli/cli.py -m "fix(cli): resolve exit code"
  ```

### 3. Freeze a Phase
Freeze a development phase and tag it using Seed Freeze:
```bash
seed freeze -p 10
```

## Runtime Verification Stamp & Workflow

The Repository Guardian uses a local directory `.seed/` containing `verification.json` to store the verification stamp.

* **Local runtime metadata**: `.seed/` contains local runtime verification stamps that must never be committed. It is intentionally excluded from Git in `.gitignore`.
* **Zero personal information**: The stamp stores only the health status, tool name, current Git HEAD, a UTC timestamp, and format schema version. It never stores absolute paths, usernames, or machine-specific filesystem information.
* **Commit Enforcement**: The `seed commit` tool enforces quality gates by verifying the verification stamp *before* staging or committing any files.
* **Verification Invalidation**: The stamp becomes automatically invalid whenever:
  - Any tracked file is modified, deleted, or staged.
  - The Git HEAD changes.
  Untracked files do *not* invalidate the verification stamp.

### Recommended Developer Workflow

To ensure only verified code reaches the repository, developers should follow this sequential workflow:

1. **Implement changes** in the codebase.
2. **Run verification**:
   ```bash
   uv run seed status
   ```
3. **Fix any failures** if any quality gate reports errors.
4. **Achieve healthy state**: once all gates pass, the repository status becomes `HEALTHY`, and the verification stamp is created/updated.
5. **Commit verified changes**:
   ```bash
   uv run seed commit
   ```
