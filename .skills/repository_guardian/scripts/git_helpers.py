"""Git helper functions for the Repository Guardian Skill."""

# ruff: noqa: S603, S607, UP022, RUF013, S110

import subprocess
from pathlib import Path


def get_repo_root() -> Path:
    """Get the absolute path to the repository root."""
    return Path(__file__).resolve().parents[3]


def is_git_repository() -> bool:
    """Check if the current workspace is a Git repository."""
    root = get_repo_root()
    if (root / ".git").exists():
        return True
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def has_merge_conflicts() -> bool:
    """Check if there are any active merge conflict markers in the repository."""
    root = get_repo_root()
    try:
        # 1. Use git to check for unmerged paths
        res = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return True

        # 2. Heuristically check changed files for conflict markers
        res_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res_status.returncode == 0:
            for line in res_status.stdout.splitlines():
                if len(line) > 3:
                    file_path = root / line[3:].strip()
                    if file_path.exists() and file_path.is_file():
                        try:
                            content = file_path.read_text(
                                encoding="utf-8", errors="ignore"
                            )
                            for content_line in content.splitlines():
                                if (
                                    content_line.startswith("<<<<<<<")
                                    or content_line == "======="
                                    or content_line.startswith(">>>>>>>")
                                ):
                                    return True
                        except Exception:
                            pass
    except Exception:
        pass
    return False


def get_git_status() -> str:
    """Get the full git status output."""
    root = get_repo_root()
    try:
        res = subprocess.run(
            ["git", "status"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return res.stdout if res.returncode == 0 else "Error running git status"
    except Exception as e:
        return f"Error: {e}"


def get_git_status_short() -> str:
    """Get the git status short summary."""
    root = get_repo_root()
    try:
        res = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return res.stdout if res.returncode == 0 else ""
    except Exception:
        return ""


def stage_files(files: list[str] | None = None) -> None:
    """Stage files for commit. Defaults to all changes if files is None."""
    root = get_repo_root()
    cmd = ["git", "add", "."] if not files else ["git", "add", *files]
    subprocess.run(
        cmd,
        cwd=str(root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def create_commit(message: str) -> str:
    """Create a git commit and return the commit hash."""
    root = get_repo_root()
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    # Get the latest commit hash
    res_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return res_hash.stdout.strip()


def create_tag(tag_name: str, message: str) -> None:
    """Create a git tag."""
    root = get_repo_root()
    subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", message],
        cwd=str(root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
