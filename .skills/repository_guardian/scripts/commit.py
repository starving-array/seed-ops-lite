"""Commit runner enforcing quality checks and Conventional Commits."""

# ruff: noqa: T201

import argparse
import re
import sys

from git_helpers import (
    create_commit,
    get_git_status_short,
    get_repo_root,
    stage_files,
)
from verification import (
    get_git_head,
    get_tracked_changes_state,
    read_verification_stamp,
)


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

    # 1. Read and Validate Verification Stamp
    repo_root = get_repo_root()
    stamp = read_verification_stamp(repo_root)

    if stamp is None:
        print("Repository verification not found.")
        print("\nRun:\n")
        print("  uv run seed status\n")
        print("before committing.")
        sys.exit(1)

    if not stamp.get("healthy"):
        print("Repository is not verified.")
        print("\nRun:\n")
        print("  uv run seed status\n")
        print("after fixing the repository.")
        sys.exit(1)

    # Validate stored Git HEAD and tracked changes state
    current_head = get_git_head(repo_root)
    stored_head = stamp.get("git_head")
    current_changes = get_tracked_changes_state(repo_root)
    stored_changes = stamp.get("tracked_changes", {})

    if stored_head != current_head or current_changes != stored_changes:
        print("Repository verification is no longer valid.")
        print("\nThe repository has changed since the last successful verification.\n")
        print("Run:\n")
        print("  uv run seed status\n")
        print("before committing.")
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
