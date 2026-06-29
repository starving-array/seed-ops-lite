"""Tests for the Repository Guardian Skill."""

# ruff: noqa: E402, T201

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add skill script directory to system path
skill_dir = (
    Path(__file__).resolve().parents[1] / ".skills" / "repository_guardian" / "scripts"
)
if str(skill_dir) not in sys.path:
    sys.path.insert(0, str(skill_dir))

import commit
from commit import (
    generate_conventional_commit_message,
    validate_conventional_commit,
)
from git_helpers import is_git_repository
from quality_check import get_venv_tool
from verification import (
    get_tracked_changes_state,
    invalidate_verification_stamp,
    read_verification_stamp,
    write_verification_stamp,
)


def test_validate_conventional_commit() -> None:
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


def test_generate_conventional_commit_message() -> None:
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


def test_get_venv_tool() -> None:
    """Verify resolution of virtualenv executables."""
    tool_path = get_venv_tool("ruff")
    assert "ruff" in tool_path.lower()


def test_is_git_repository() -> None:
    """Verify detection of the git repository status."""
    assert is_git_repository() is True


# ============================================================================
# NEW TESTS: Verification Stamp and Change Detection (RG-1 to RG-3)
# ============================================================================


def test_write_verification_stamp(tmp_path: Path) -> None:
    """Verify verification.json is created and follows the expected schema."""
    with (
        patch("verification.get_git_head", return_value="fake_head_hash"),
        patch(
            "verification.get_tracked_changes_state", return_value={"file.py": "hash"}
        ),
    ):
        write_verification_stamp(tmp_path)

    stamp_path = tmp_path / ".seed" / "verification.json"
    assert stamp_path.exists()

    with stamp_path.open(encoding="utf-8") as f:
        data = json.load(f)

    assert data["healthy"] is True
    assert data["git_head"] == "fake_head_hash"
    assert data["tool"] == "seed status"
    assert data["schema_version"] == 1
    assert data["tracked_changes"] == {"file.py": "hash"}
    assert "generated_at" in data
    # Absolute repository path should NOT be stored (RG-2.1)
    assert "repository" not in data


def test_invalidate_verification_stamp(tmp_path: Path) -> None:
    """Verify verification.json is deleted or invalidated when requested."""
    seed_dir = tmp_path / ".seed"
    seed_dir.mkdir(exist_ok=True)
    stamp_path = seed_dir / "verification.json"
    stamp_path.write_text("{}", encoding="utf-8")

    assert stamp_path.exists()
    invalidate_verification_stamp(tmp_path)
    assert not stamp_path.exists()


def test_read_verification_stamp_corrupted(tmp_path: Path) -> None:
    """Verify corrupted verification.json is handled gracefully and returns None."""
    seed_dir = tmp_path / ".seed"
    seed_dir.mkdir(exist_ok=True)
    stamp_path = seed_dir / "verification.json"

    # Invalid JSON syntax
    stamp_path.write_text("{invalid json", encoding="utf-8")
    assert read_verification_stamp(tmp_path) is None

    # Missing file
    stamp_path.unlink()
    assert read_verification_stamp(tmp_path) is None


def test_write_verification_stamp_recreates_directory(tmp_path: Path) -> None:
    """Verify missing .seed directory is recreated correctly during stamp write."""
    seed_dir = tmp_path / ".seed"
    assert not seed_dir.exists()

    with patch("verification.get_git_head", return_value="head_hash"):
        write_verification_stamp(tmp_path)

    assert seed_dir.exists()
    assert (seed_dir / "verification.json").exists()


def test_get_tracked_changes_state() -> None:
    """Verify change detection under different git porcelain outputs."""
    # Scenario: Modifying a tracked file, deleting a file, untracked, and ignored files
    git_porcelain = (
        " M app/api/endpoints/schema.py\n"
        " D tests/test_e2e_workflow.py\n"
        "?? untracked_temp.txt\n"
        "!! ignored_temp.txt\n"
        "R  old_name.py -> new_name.py\n"
    )

    fake_run = MagicMock()
    fake_run.returncode = 0
    fake_run.stdout = git_porcelain

    with (
        patch("subprocess.run", return_value=fake_run),
        patch("verification.get_file_sha256", return_value="fake_sha256"),
    ):
        changes = get_tracked_changes_state(Path("/fake/repo"))

    # Assert modified tracked file is captured
    assert "app/api/endpoints/schema.py" in changes
    assert changes["app/api/endpoints/schema.py"] == "fake_sha256"

    # Assert deleted tracked file is captured as 'deleted'
    assert "tests/test_e2e_workflow.py" in changes
    assert changes["tests/test_e2e_workflow.py"] == "deleted"

    # Assert rename destination file is captured
    assert "new_name.py" in changes
    assert changes["new_name.py"] == "fake_sha256"

    # Assert untracked and ignored files do NOT invalidate/show up in tracked changes
    assert "untracked_temp.txt" not in changes
    assert "ignored_temp.txt" not in changes


# ============================================================================
# NEW TESTS: Commit Enforcement (RG-2 to RG-4)
# ============================================================================


def test_commit_with_valid_stamp() -> None:
    """Verify commit succeeds when verification stamp is valid."""
    fake_stamp = {
        "healthy": True,
        "git_head": "valid_head_hash",
        "tracked_changes": {},
    }

    with (
        patch("commit.read_verification_stamp", return_value=fake_stamp),
        patch("commit.get_git_head", return_value="valid_head_hash"),
        patch("commit.get_tracked_changes_state", return_value={}),
        patch("commit.stage_files") as mock_stage,
        patch("commit.create_commit", return_value="commit_hash") as mock_commit,
        patch("sys.argv", ["commit", "-m", "feat: commit success"]),
        pytest.raises(SystemExit) as exc,
    ):
        commit.main()

    assert exc.value.code == 0
    mock_stage.assert_called_once()
    mock_commit.assert_called_once_with("feat: commit success")


def test_commit_fails_when_missing_stamp(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify commit fails with helpful instructions when stamp is missing."""
    with (
        patch("commit.read_verification_stamp", return_value=None),
        patch("sys.argv", ["commit", "-m", "feat: missing stamp"]),
        pytest.raises(SystemExit) as exc,
    ):
        commit.main()

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Repository verification stamp not found." in captured.out
    assert "uv run seed status" in captured.out


def test_commit_fails_when_unhealthy_stamp(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify commit fails with helpful instructions when stamp is unhealthy."""
    fake_stamp = {
        "healthy": False,
        "git_head": "valid_head_hash",
        "tracked_changes": {},
    }

    with (
        patch("commit.read_verification_stamp", return_value=fake_stamp),
        patch("sys.argv", ["commit", "-m", "feat: unhealthy stamp"]),
        pytest.raises(SystemExit) as exc,
    ):
        commit.main()

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Repository is in an unhealthy state." in captured.out
    assert "uv run seed status" in captured.out


def test_commit_fails_when_outdated_or_changed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify commit fails when repository or HEAD has changed since validation."""
    fake_stamp = {
        "healthy": True,
        "git_head": "head_hash_v1",
        "tracked_changes": {"app.py": "sha1"},
    }

    # Case A: HEAD mismatched
    with (
        patch("commit.read_verification_stamp", return_value=fake_stamp),
        patch("commit.get_git_head", return_value="head_hash_v2"),
        patch("commit.get_tracked_changes_state", return_value={"app.py": "sha1"}),
        patch("sys.argv", ["commit", "-m", "feat: outdated head"]),
        pytest.raises(SystemExit) as exc,
    ):
        commit.main()

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Repository verification is no longer valid." in captured.out
    assert "uv run seed status" in captured.out

    # Case B: Tracked changes mismatched (file modified)
    with (
        patch("commit.read_verification_stamp", return_value=fake_stamp),
        patch("commit.get_git_head", return_value="head_hash_v1"),
        patch("commit.get_tracked_changes_state", return_value={"app.py": "sha2"}),
        patch("sys.argv", ["commit", "-m", "feat: outdated changes"]),
        pytest.raises(SystemExit) as exc,
    ):
        commit.main()

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Repository verification is no longer valid." in captured.out
    assert "uv run seed status" in captured.out


def test_security_audit_api() -> None:
    """Verify that security_audit loads and run_security_audit returns a valid result."""
    import security_audit

    with (
        patch("security_audit.get_repo_files", return_value=[]),
        patch("security_audit.is_file_ignored", return_value=True),
    ):
        result = security_audit.run_security_audit()
    assert result.success is True
    assert "No secrets detected" in result.message
    assert isinstance(result.details, list)


def test_repository_status_calls_security_audit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify that repository_status imports and runs the security audit module."""
    import repository_status
    import security_audit

    fake_result = security_audit.SecurityAuditResult(
        success=True,
        message="Mock security audit passed",
        details=["detail 1", "detail 2"],
    )

    with (
        patch("repository_status.is_git_repository", return_value=True),
        patch("repository_status.get_git_status", return_value="clean"),
        patch(
            "security_audit.run_security_audit", return_value=fake_result
        ) as mock_audit,
        patch("repository_status.write_verification_stamp"),
        patch("repository_status.run_command", return_value=(True, "", "")),
        patch("sys.argv", ["status"]),
        pytest.raises(SystemExit) as exc,
    ):
        repository_status.main()

    assert exc.value.code == 0
    mock_audit.assert_called_once()
    captured = capsys.readouterr()
    assert "Mock security audit passed" in captured.out
    assert "detail 1" in captured.out
    assert "detail 2" in captured.out


def test_repository_status_security_audit_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify that repository_status handles security audit failures correctly."""
    import repository_status
    import security_audit

    fake_result = security_audit.SecurityAuditResult(
        success=False,
        message="Mock security audit failed",
        details=["vulnerability found"],
    )

    with (
        patch("repository_status.is_git_repository", return_value=True),
        patch("repository_status.get_git_status", return_value="clean"),
        patch(
            "security_audit.run_security_audit", return_value=fake_result
        ) as mock_audit,
        patch("repository_status.invalidate_verification_stamp"),
        patch("sys.argv", ["status"]),
        pytest.raises(SystemExit) as exc,
    ):
        repository_status.main()

    assert exc.value.code == 1
    mock_audit.assert_called_once()
    captured = capsys.readouterr()
    assert "Mock security audit failed" in captured.out
    assert "vulnerability found" in captured.out
    assert "Security audit failed" in captured.err
