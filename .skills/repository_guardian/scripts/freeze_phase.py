"""Freeze Current Phase automation script."""

# ruff: noqa: T201, S110

import argparse
import json
import sys
import time
from typing import Any

from git_helpers import (
    create_commit,
    create_tag,
    get_repo_root,
    stage_files,
)
from quality_check import execute_quality_checks


def main() -> None:
    """Freeze a specific project development phase."""
    parser = argparse.ArgumentParser(description="Repository Guardian Phase Freezer")
    parser.add_argument(
        "-p",
        "--phase",
        required=True,
        help="The name or number of the phase to freeze (e.g. '10' or 'phase-10')",
    )
    args = parser.parse_args()

    phase_clean = str(args.phase).strip()
    if not phase_clean:
        print("Error: Phase name cannot be empty.", file=sys.stderr)
        sys.exit(1)

    root = get_repo_root()
    frozen_file = root / ".frozen_phases.json"

    # 1. Update .frozen_phases.json file
    print(f"Freezing phase '{phase_clean}'...")
    phases_data: dict[str, Any] = {"frozen_phases": []}
    if frozen_file.exists():
        try:
            with frozen_file.open("r", encoding="utf-8") as f:
                phases_data = json.load(f)
        except Exception:
            pass

    # Check if already frozen
    existing_phases = [p["phase"] for p in phases_data.get("frozen_phases", [])]
    if phase_clean in existing_phases:
        print(f"Phase '{phase_clean}' is already recorded as frozen.")
    else:
        phases_data.setdefault("frozen_phases", []).append(
            {
                "phase": phase_clean,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        try:
            with frozen_file.open("w", encoding="utf-8") as f:
                json.dump(phases_data, f, indent=2)
            print(f"Updated {frozen_file.name}")
        except Exception as e:
            print(f"Error updating frozen phases registry: {e}", file=sys.stderr)
            sys.exit(1)

    # 2. Run Quality Gate Checks
    print("Running quality gate verification...")
    success, failures = execute_quality_checks()
    if not success:
        print("Phase freeze aborted due to quality check failures:", file=sys.stderr)
        for fail in failures:
            print(f"- {fail}", file=sys.stderr)
        sys.exit(1)

    # 3. Stage and Commit the frozen phases file
    try:
        stage_files([str(frozen_file.relative_to(root))])
    except Exception as e:
        print(f"Error staging files: {e}", file=sys.stderr)
        sys.exit(1)

    commit_msg = f"chore(release): freeze phase {phase_clean}"
    try:
        commit_hash = create_commit(commit_msg)
        print(f"Created commit: {commit_hash}")
    except Exception as e:
        # Check if there were no changes to commit
        if "nothing to commit" in str(e).lower() or "no changes" in str(e).lower():
            print("Nothing new to commit.")
        else:
            print(f"Error committing freeze: {e}", file=sys.stderr)
            sys.exit(1)

    # 4. Create Git Tag
    tag_name = f"phase-{phase_clean}"
    try:
        create_tag(tag_name, f"Freeze of phase {phase_clean}")
        print(f"Successfully tagged commit as '{tag_name}'")
        sys.exit(0)
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"Tag '{tag_name}' already exists in Git. Skipping tag creation.")
            sys.exit(0)
        else:
            print(f"Error tagging commit: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
