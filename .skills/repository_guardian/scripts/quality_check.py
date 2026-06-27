"""Quality check gate executor for the Repository Guardian Skill."""

# ruff: noqa: T201, S603, UP022

import subprocess
import sys
from pathlib import Path

from git_helpers import get_repo_root, has_merge_conflicts, is_git_repository


def run_command(cmd: list[str], cwd: Path) -> tuple[bool, str, str]:
    """Run a subprocess command and return success and output streams."""
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        return False, "", f"Failed to run command {' '.join(cmd)}: {e}"


def get_venv_tool(tool_name: str) -> str:
    """Resolve path to virtual environment tool executable."""
    root = get_repo_root()
    # Windows style venv Scripts folder
    win_path = root / ".venv" / "Scripts" / f"{tool_name}.exe"
    if win_path.exists():
        return str(win_path)
    win_path_no_exe = root / ".venv" / "Scripts" / tool_name
    if win_path_no_exe.exists():
        return str(win_path_no_exe)

    # Unix style venv bin folder
    unix_path = root / ".venv" / "bin" / tool_name
    if unix_path.exists():
        return str(unix_path)

    return tool_name  # Fallback to system path


def execute_quality_checks() -> tuple[bool, list[str]]:
    """Run git repository and code quality checks (Ruff, Black, MyPy, Pytest)."""
    root = get_repo_root()
    failures = []

    # 1. Verify Git Repository
    if not is_git_repository():
        failures.append("Not a Git repository.")
        return False, failures

    # 2. Verify No Merge Conflicts
    if has_merge_conflicts():
        failures.append("Merge conflicts detected in the repository.")
        return False, failures

    # 3. Run Ruff Check
    ruff_cmd = [get_venv_tool("ruff"), "check", "app/", "tests/"]
    success, stdout, stderr = run_command(ruff_cmd, root)
    if not success:
        failures.append(
            f"Ruff lint checks failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    # 4. Run Black Formatter Check
    black_cmd = [get_venv_tool("black"), "--check", "app/", "tests/"]
    success, stdout, stderr = run_command(black_cmd, root)
    if not success:
        failures.append(
            f"Black formatting check failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    # 5. Run MyPy Type Check
    mypy_cmd = [get_venv_tool("mypy"), "app/"]
    success, stdout, stderr = run_command(mypy_cmd, root)
    if not success:
        failures.append(
            f"MyPy static type checks failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    # 6. Run Pytest Suite
    pytest_cmd = [get_venv_tool("pytest")]
    success, stdout, stderr = run_command(pytest_cmd, root)
    if not success:
        failures.append(
            f"Pytest suite checks failed.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    return len(failures) == 0, failures


if __name__ == "__main__":
    success, failures = execute_quality_checks()
    if success:
        print("All quality checks passed successfully!")
        sys.exit(0)
    else:
        print("Quality checks failed!", file=sys.stderr)
        for fail in failures:
            print(f"- {fail}", file=sys.stderr)
        sys.exit(1)
