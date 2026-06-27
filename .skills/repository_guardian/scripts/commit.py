"""Commit runner enforcing quality checks and Conventional Commits."""

# ruff: noqa: T201

import argparse
import re
import sys

from git_helpers import (
    create_commit,
    get_git_status_short,
    stage_files,
)
from quality_check import execute_quality_checks


def validate_conventional_commit(msg: str) -> bool:
    """Validate if message follows Conventional Commits format."""
    pattern = r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-zA-Z0-9_-]+\))?: .+"
    return bool(re.match(pattern, msg))


def generate_conventional_commit_message() -> str:
    """Generate a Conventional Commit message based on changed files."""
    status_short = get_git_status_short()
    if not status_short:
        return "chore: no changes detected"

    files_modified = []
    for line in status_short.splitlines():
        if len(line) > 3:
            files_modified.append(line[3:].strip())

    if not files_modified:
        return "chore: repository update"

    cli_files = [f for f in files_modified if "cli" in f and "test" not in f]
    test_files = [f for f in files_modified if "test" in f]
    doc_files = [f for f in files_modified if f.endswith(".md") or "docs" in f]
    config_files = [
        f
        for f in files_modified
        if "config" in f
        or f.endswith(".json")
        or f.endswith(".yaml")
        or f.endswith(".toml")
    ]

    msg = "chore: general repository updates"
    if cli_files:
        msg = "feat(cli): updates to CLI components"
    elif test_files and not any(
        f for f in files_modified if "app/" in f and "test" not in f
    ):
        msg = "test: update repository test cases"
    elif doc_files and not any(f for f in files_modified if f.endswith(".py")):
        msg = "docs: update repository documentation"
    elif config_files and not any(f for f in files_modified if f.endswith(".py")):
        msg = "chore(config): update configuration parameters"

    return msg


def main() -> None:
    """Execute quality checks and perform Conventional Commit."""
    parser = argparse.ArgumentParser(description="Repository Guardian Commit Tool")
    parser.add_argument(
        "-m",
        "--message",
        help="Optional commit message following Conventional Commits specification",
    )
    parser.add_argument(
        "-f",
        "--files",
        nargs="+",
        help="Specific files to commit. Stages all if omitted.",
    )
    args = parser.parse_args()

    # 1. Run Quality Checks
    print("Running quality gates...")
    success, failures = execute_quality_checks()
    if not success:
        print("Commit aborted due to quality check failures:", file=sys.stderr)
        for fail in failures:
            print(f"- {fail}", file=sys.stderr)
        sys.exit(1)

    # 2. Determine Commit Message
    commit_msg = args.message
    if commit_msg:
        if not validate_conventional_commit(commit_msg):
            print(
                f"Error: Commit message '{commit_msg}' does not match "
                "Conventional Commits format (e.g. 'feat(scope): description').",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        commit_msg = generate_conventional_commit_message()
        print(f"No commit message provided. Generated: '{commit_msg}'")

    # 3. Stage Files
    try:
        stage_files(args.files)
    except Exception as e:
        print(f"Error staging files: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. Perform Commit
    try:
        commit_hash = create_commit(commit_msg)
        print("Commit created successfully!")
        print(f"Hash: {commit_hash}")
        sys.exit(0)
    except Exception as e:
        print(f"Error creating commit: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
