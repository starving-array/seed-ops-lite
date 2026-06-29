"""Repository status and health check reporting tool."""

# ruff: noqa: T201, ERA001, S603, S607, UP022

import sys
import time

from git_helpers import (
    get_git_status,
    get_repo_root,
    is_git_repository,
)
from quality_check import get_venv_tool, run_command
from verification import (
    invalidate_verification_stamp,
    write_verification_stamp,
)


def main() -> None:
    """Print Git status, conflicts, and quality gate health diagnostics."""
    print("==================================================")
    print("                 SEED CLI STATUS                  ")
    print("==================================================")

    root = get_repo_root()

    # --------------------------------------------------
    # SECTION: Repository
    # --------------------------------------------------
    print("\n--- [Repository] ---")
    print(f"Path: {root}")

    # Git Repository Verification
    if not is_git_repository():
        print("Status:  [FAIL] (Not a Git repository)", file=sys.stderr)
        print("\n--- [Verification] ---", file=sys.stderr)
        invalidate_verification_stamp(root)
        print("Repository Status: UNHEALTHY", file=sys.stderr)
        print("\nVerification stamp removed.", file=sys.stderr)
        print(
            "The repository verification is invalid because it is not a Git repository.",
            file=sys.stderr,
        )
        print("\nPlease initialize a Git repository and run:", file=sys.stderr)
        print("\n  uv run seed status\n", file=sys.stderr)
        print("to perform quality checks and create the stamp.", file=sys.stderr)

        print("\n--- [Summary] ---", file=sys.stderr)
        print("Seed Status:  Failed (Not a Git repository)", file=sys.stderr)
        sys.exit(1)
    print("Status:  [PASS] (Git repository detected)")

    # Git Status Summary
    status_out = get_git_status()
    print("Git Status Summary:")
    print("  " + "\n  ".join(status_out.strip().splitlines()))

    # --------------------------------------------------
    # SECTION: Security
    # --------------------------------------------------
    print("\n--- [Security] ---")
    from security_audit import run_security_audit

    audit_res = run_security_audit()
    print(audit_res.message)
    for detail in audit_res.details:
        print(f"  {detail}")
    if not audit_res.success:
        print("\n--- [Verification] ---", file=sys.stderr)
        invalidate_verification_stamp(root)
        print("Repository Status: UNHEALTHY", file=sys.stderr)
        print("\nVerification stamp removed.", file=sys.stderr)
        print(
            "The repository verification is invalid because security audits failed.",
            file=sys.stderr,
        )
        print("\nPlease fix the security vulnerabilities and run:", file=sys.stderr)
        print("\n  uv run seed status\n", file=sys.stderr)
        print("to perform quality checks and recreate the stamp.", file=sys.stderr)

        print("\n--- [Summary] ---", file=sys.stderr)
        print("Seed Status:  Failed (Security audit failed)", file=sys.stderr)
        sys.exit(1)

    # --------------------------------------------------
    # SECTION: Quality Gates
    # --------------------------------------------------
    print("\n--- [Quality Gates] ---")
    print("Executing live validations...")

    gates = [
        ("Ruff", [get_venv_tool("ruff"), "check", "app/", "tests/"]),
        ("Black", [get_venv_tool("black"), "--check", "app/", "tests/"]),
        ("MyPy", [get_venv_tool("mypy"), "app/"]),
        ("Pytest", [get_venv_tool("pytest")]),
    ]

    total_gates = len(gates)
    for i, (name, cmd) in enumerate(gates, 1):
        print(f"[{i}/{total_gates}] Running {name}... ", end="", flush=True)
        start_time = time.time()
        success, stdout, stderr = run_command(cmd, root)
        elapsed = time.time() - start_time

        if success:
            print(f" [PASS] ({elapsed:.2f}s)")
        else:
            print(f" [FAIL] ({elapsed:.2f}s)", file=sys.stderr)
            print(
                "\n==================================================",
                file=sys.stderr,
            )
            print(f"Error: {name} Quality Gate Failed!", file=sys.stderr)
            print(
                "==================================================",
                file=sys.stderr,
            )
            print(f"Failed Command: {' '.join(cmd)}", file=sys.stderr)
            if stdout:
                print(f"STDOUT:\n{stdout}", file=sys.stderr)
            if stderr:
                print(f"STDERR:\n{stderr}", file=sys.stderr)

            print("\n--- [Verification] ---", file=sys.stderr)
            invalidate_verification_stamp(root)
            print("Repository Status: UNHEALTHY", file=sys.stderr)
            print("\nVerification stamp removed.", file=sys.stderr)
            print(
                "The repository verification is invalid because the checks failed.",
                file=sys.stderr,
            )
            print("\nPlease fix the failures and run:", file=sys.stderr)
            print("\n  uv run seed status\n", file=sys.stderr)
            print("to perform quality checks and recreate the stamp.", file=sys.stderr)

            print("\n--- [Summary] ---", file=sys.stderr)
            print("Seed Status:  Failed (Quality gate aborted)", file=sys.stderr)
            sys.exit(1)

    # --------------------------------------------------
    # SECTION: Verification
    # --------------------------------------------------
    print("\n--- [Verification] ---")
    write_verification_stamp(root)
    print("Repository Status: HEALTHY")
    print("\nVerification stamp created successfully.")
    print("The repository is now verified and ready for commit.")

    # --------------------------------------------------
    # SECTION: Summary
    # --------------------------------------------------
    print("\n--- [Summary] ---")
    print("Seed Status:  Passed (HEALTHY - All checks pass)")
    print("==================================================")
    sys.exit(0)


if __name__ == "__main__":
    main()
