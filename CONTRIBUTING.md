# Contributing to SafeSeed-Ops

Thank you for your interest in contributing to SafeSeed-Ops! To maintain a highly secure, reliable, and standardized code foundation, all contributors must follow the guidelines detailed below.

---

## 1. The Seed Workflow Requirement

All repository operations—specifically checking status, committing modifications, and freezing development phases—must be executed using the **Seed** engineering workflow. 

Before staging or committing any code, you must run the local verification suite:
* **Seed Status**: `python .skills/repository_guardian/scripts/repository_status.py`
* **Seed Commit**: `python .skills/repository_guardian/scripts/commit.py`

Direct git commits (via `git commit`) are forbidden for standard development and will fail repository audit policies.

---

## 2. Branch Naming Conventions

Always develop in a feature or fix branch cut from the latest `main` branch. Use clear, scoped branch names:
* Features: `feat/feature-name` (e.g., `feat/cli-file-checks`)
* Bug fixes: `fix/bug-name` (e.g., `fix/exit-codes`)
* Refactoring: `refactor/scope-name`
* Documentation: `docs/doc-topic`
* Chores/Maintenance: `chore/maintenance-topic`

---

## 3. Conventional Commits

Your commit messages must conform to the **Conventional Commits** specification. The Seed Commit command enforces this format automatically. Format:
```
<type>(<scope>): <short description>
```
Allowed types:
* `feat`: A new user-facing feature.
* `fix`: A bug fix.
* `docs`: Documentation changes only.
* `style`: Code formatting changes only (e.g. Black).
* `refactor`: Code restructuring without functional changes.
* `perf`: Code changes improving performance.
* `test`: Adding or correcting tests.
* `build`: Build system or dependency updates.
* `ci`: Continuous Integration files/scripts updates.
* `chore`: Auxiliary chores or configuration updates.
* `revert`: Reverting a previous commit.

---

## 4. Coding & Quality Standards

Every contribution must pass the quality gates before being accepted:
1. **Formatting**: Code must be formatted using **Black**.
2. **Linting**: Code must be lint-clean under **Ruff**.
3. **Typing**: Code must be fully typed and pass **MyPy** analysis.
4. **Testing**: All unit and integration tests must pass cleanly under **Pytest**.

---

## 5. Documentation Expectations

* Update relevant markdown guides (such as [README.md](file:///C:/Users/lovea/Documents/hackathon/safeseedops-lite/README.md) or [docs/architecture/ai_platform_architecture.md](file:///C:/Users/lovea/Documents/hackathon/safeseedops-lite/docs/architecture/ai_platform_architecture.md)) if your change introduces new CLI options, system configs, or data schemas.
* Preserve all inline Python comments and docstrings.

---

## 6. Pull Request Expectations

1. Cut a branch using correct naming conventions.
2. Develop changes incrementally.
3. Validate and commit using the Seed workflow.
4. Open a Pull Request (PR) targeting the `main` branch.
5. Ensure the description outlines the changes and links to the relevant issue.
6. Verify that upstream GitHub actions/CI workflows run and pass successfully.

---

## 7. Issue Reporting

If you encounter bugs, security vulnerabilities, or have feature proposals:
* Open a GitHub issue outlining step-by-step reproduction guidelines, actual vs. expected results, and environment settings.
* For security concerns, report them privately according to our security policies.
