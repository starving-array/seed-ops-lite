"""Repository status and health check reporting tool."""

# ruff: noqa: T201, ERA001, S603, S607, UP022

import subprocess
import sys
import time

from git_helpers import (
    get_git_status,
    get_repo_root,
    has_merge_conflicts,
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
        print("Status:  Failed (Not a Git repository)", file=sys.stderr)
        invalidate_verification_stamp(root)
        print("\nRepository Status: UNHEALTHY\n\nVerification stamp removed.")
        sys.exit(1)
    print("Status:  Passed (Git repository detected)")

    # Git Status Summary
    status_out = get_git_status()
    print("Git Status Summary:")
    print("  " + "\n  ".join(status_out.strip().splitlines()))

    # --------------------------------------------------
    # SECTION: Security
    # --------------------------------------------------
    print("\n--- [Security] ---")

    # Merge Conflict Detection
    if has_merge_conflicts():
        print(
            "Merge Conflicts:  Failed (Active conflict markers detected!)",
            file=sys.stderr,
        )
        print("Please resolve conflicts before making commits.", file=sys.stderr)
        invalidate_verification_stamp(root)
        print("\nRepository Status: UNHEALTHY\n\nVerification stamp removed.")
        sys.exit(1)
    print("Merge Conflicts:  Passed (None detected)")

    # Secret Scanning (.env ignore check)
    dot_env_path = root / ".env"
    if dot_env_path.exists():
        res = subprocess.run(
            ["git", "check-ignore", ".env"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            print("Secret Scan:      Passed (.env file successfully ignored)")
        else:
            print(
                "Secret Scan:      Failed (.env file is NOT ignored in .gitignore!)",
                file=sys.stderr,
            )
            invalidate_verification_stamp(root)
            print("\nRepository Status: UNHEALTHY\n\nVerification stamp removed.")
            sys.exit(1)
    else:
        print("Secret Scan:      Passed (No local .env file found)")

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
            print(f" Passed ({elapsed:.2f}s)")
        else:
            print(f" Failed ({elapsed:.2f}s)", file=sys.stderr)
            print(
                "\n==================================================",
                file=sys.stderr,
            )
            print(f"Error: {name} Quality Gate Failed!", file=sys.stderr)
            print(
                "==================================================",
                file=sys.stderr,
            )
            if stdout:
                print(f"STDOUT:\n{stdout}", file=sys.stderr)
            if stderr:
                print(f"STDERR:\n{stderr}", file=sys.stderr)
            print("\n--- [Summary] ---")
            print("Seed Status:  Failed (Quality gate aborted)", file=sys.stderr)
            invalidate_verification_stamp(root)
            print("\nRepository Status: UNHEALTHY\n\nVerification stamp removed.")
            sys.exit(1)

    # --------------------------------------------------
    # SECTION: Summary
    # --------------------------------------------------
    print("\n--- [Summary] ---")
    print("Seed Status:  Passed (HEALTHY - All checks pass)")
    print("==================================================")
    write_verification_stamp(root)
    print("\nRepository Status: HEALTHY\n\nVerification stamp created.")
    sys.exit(0)


if __name__ == "__main__":
    main()
