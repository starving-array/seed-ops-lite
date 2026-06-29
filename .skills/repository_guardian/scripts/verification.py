"""Repository verification stamp manager."""

# ruff: noqa: T201, S603, S607, UP022

import hashlib
import json
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def get_git_head(repo_root: Path) -> str:
    """Get the current HEAD commit hash from Git."""
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if res.returncode == 0:
        return res.stdout.strip()
    return "unknown"


def get_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    if not file_path.exists():
        return "deleted"
    try:
        sha256 = hashlib.sha256()
        with file_path.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256.update(byte_block)
        return sha256.hexdigest()
    except Exception:
        return "error"


def get_tracked_changes_state(repo_root: Path) -> dict[str, str]:
    """Get the current state of dirty tracked files."""
    state: dict[str, str] = {}
    with suppress(Exception):
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if not line or len(line) < 4:
                    continue
                status_code = line[:2]
                file_path_str = line[3:].strip()
                # If it's a rename, parse the destination path
                if " -> " in file_path_str:
                    file_path_str = file_path_str.split(" -> ")[-1].strip()

                # Skip untracked (??) and ignored (!!) files
                if status_code in ("??", "!!"):
                    continue

                # Check if it is a deleted file
                if "D" in status_code:
                    state[file_path_str] = "deleted"
                else:
                    full_path = repo_root / file_path_str
                    state[file_path_str] = get_file_sha256(full_path)
    return state


def write_verification_stamp(repo_root: Path) -> None:
    """Write the verification.json stamp to the .seed directory."""
    seed_dir = repo_root / ".seed"
    seed_dir.mkdir(exist_ok=True)

    stamp_path = seed_dir / "verification.json"
    git_head = get_git_head(repo_root)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    stamp_data = {
        "healthy": True,
        "git_head": git_head,
        "generated_at": timestamp,
        "tool": "seed status",
        "schema_version": 1,
        "tracked_changes": get_tracked_changes_state(repo_root),
    }

    with stamp_path.open("w", encoding="utf-8") as f:
        json.dump(stamp_data, f, indent=4)


def invalidate_verification_stamp(repo_root: Path) -> None:
    """Remove the verification.json stamp if it exists."""
    stamp_path = repo_root / ".seed" / "verification.json"
    if stamp_path.exists():
        with suppress(OSError):
            stamp_path.unlink()


def read_verification_stamp(repo_root: Path) -> dict[str, Any] | None:
    """Read and parse the verification.json stamp if it exists."""
    stamp_path = repo_root / ".seed" / "verification.json"
    if not stamp_path.exists():
        return None
    try:
        with stamp_path.open(encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return None
