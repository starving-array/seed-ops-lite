"""Tests for the Repository Guardian Skill."""

# ruff: noqa: E402

import sys
from pathlib import Path
from unittest.mock import patch

# Add skill script directory to system path
skill_dir = (
    Path(__file__).resolve().parents[1] / ".skills" / "repository_guardian" / "scripts"
)
if str(skill_dir) not in sys.path:
    sys.path.insert(0, str(skill_dir))

from commit import generate_conventional_commit_message, validate_conventional_commit
from git_helpers import is_git_repository
from quality_check import get_venv_tool


def test_validate_conventional_commit():
    """Verify that commit messages are correctly validated against Conventional Commits."""
    assert validate_conventional_commit("feat(cli): add file check")
    assert validate_conventional_commit("fix: resolve logic bug")
    assert validate_conventional_commit("chore(config): update version")
    assert validate_conventional_commit("docs: update README")
    assert validate_conventional_commit("test: add integration test cases")

    # Invalid formats
    assert not validate_conventional_commit("feat add file check")
    assert not validate_conventional_commit("random update message")
    assert not validate_conventional_commit("fix(cli) missing colon")
    assert not validate_conventional_commit("chore: ")


def test_generate_conventional_commit_message():
    """Verify that a Conventional Commit message is generated correctly based on changed files."""
    # Test fallback
    with patch("commit.get_git_status_short", return_value=""):
        assert generate_conventional_commit_message() == "chore: no changes detected"

    with patch("commit.get_git_status_short", return_value=" M app/cli/cli.py"):
        assert (
            generate_conventional_commit_message()
            == "feat(cli): updates to CLI components"
        )

    with patch("commit.get_git_status_short", return_value=" M tests/test_cli.py"):
        assert (
            generate_conventional_commit_message()
            == "test: update repository test cases"
        )

    with patch("commit.get_git_status_short", return_value=" M README.md"):
        assert (
            generate_conventional_commit_message()
            == "docs: update repository documentation"
        )

    with patch("commit.get_git_status_short", return_value=" M pyproject.toml"):
        assert (
            generate_conventional_commit_message()
            == "chore(config): update configuration parameters"
        )


def test_get_venv_tool():
    """Verify resolution of virtualenv executables."""
    tool_path = get_venv_tool("ruff")
    assert "ruff" in tool_path.lower()


def test_is_git_repository():
    """Verify detection of the git repository status."""
    assert is_git_repository() is True
