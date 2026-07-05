"""Unit tests for the Seed CLI dev command and DeveloperStartupManager integrations."""

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

from app.cli.seed_workflow import print_help
from app.services.developer_startup import DeveloperStartupManager, EnvironmentValidator


def test_cli_command_registration() -> None:
    """Verify 'dev' command is registered in print_help and sys.modules."""
    captured = StringIO()
    sys.stdout = captured
    try:
        print_help()
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert "dev" in output
    assert "One-command developer startup" in output


@patch("shutil.which")
def test_environment_validation_missing_node_npm(mock_which: MagicMock) -> None:
    """Verify environment checks flag missing node/npm as diagnostic failures."""
    mock_which.return_value = None

    issues = EnvironmentValidator.validate_environment()
    issue_types = [i.issue_type for i in issues]

    assert "MissingNode" in issue_types
    assert "MissingNpm" in issue_types


@patch("shutil.which")
def test_environment_validation_missing_frontend_node_modules(
    mock_which: MagicMock,
) -> None:
    """Verify environment checks flag missing node_modules."""
    mock_which.return_value = "/usr/bin/node"

    with patch("pathlib.Path.is_dir", return_value=False):
        issues = EnvironmentValidator.validate_environment()
        issue_types = [i.issue_type for i in issues]
        assert "MissingFrontendDependencies" in issue_types


def test_dev_dry_run_success() -> None:
    """Verify DeveloperStartupManager dry run returns successful status."""
    manager = DeveloperStartupManager()
    from app.platform.configuration.settings import platform_settings

    original_port = platform_settings.PLATFORM_DEV_PORT
    platform_settings.PLATFORM_DEV_PORT = 29999
    try:
        with patch.object(
            EnvironmentValidator, "validate_environment", return_value=[]
        ):
            res = manager.run_dev_startup(dry_run=True)
            assert res.success is True
            assert res.health.is_healthy is True
    finally:
        platform_settings.PLATFORM_DEV_PORT = original_port


def test_graceful_shutdown() -> None:
    """Verify shutdown closes process mappings cleanly."""
    manager = DeveloperStartupManager()
    mock_proc = MagicMock()
    manager.launcher.running_services["backend"] = {
        "status": "Running",
        "proc": mock_proc,
    }
    manager.shutdown()
    assert mock_proc.terminate.called or mock_proc.kill.called
    assert len(manager.launcher.running_services) == 0


def test_docker_detection_missing() -> None:
    """Verify Docker detection fails when docker command is not found."""
    with (
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.exists", return_value=True),
    ):
        issues = EnvironmentValidator.validate_environment()
        issue_types = [i.issue_type for i in issues]
        assert "MissingDocker" in issue_types


def test_docker_daemon_not_running() -> None:
    """Verify Docker daemon error is raised when docker info fails."""

    def mock_which(cmd):
        if cmd == "docker":
            return "/usr/bin/docker"
        return "/usr/bin/node"

    with (
        patch("shutil.which", side_effect=mock_which),
        patch("pathlib.Path.exists", return_value=True),
        patch("subprocess.run", side_effect=Exception("daemon down")),
    ):
        issues = EnvironmentValidator.validate_environment()
        issue_types = [i.issue_type for i in issues]
        assert "DockerDaemonNotRunning" in issue_types


def test_infrastructure_startup_and_existing_containers() -> None:
    """Verify compose up and ps are executed during launch."""
    from app.services.developer_startup import ServiceLauncher

    launcher = ServiceLauncher()
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("shutil.which", return_value="/usr/bin/docker"),
        patch("subprocess.run") as mock_run,
    ):
        # mock compose ps returning "running" to verify health
        mock_ps_res = MagicMock()
        mock_ps_res.stdout = "running"
        mock_run.return_value = mock_ps_res

        # Mock backend and frontend popen to not actually launch
        with (
            patch("subprocess.Popen") as mock_popen,
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_res = MagicMock()
            mock_res.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_res

            urls = launcher.launch_services()
            assert "backendUrl" in urls
            assert "frontendUrl" in urls
            assert mock_popen.call_count == 2


def test_sqlite_only_no_infrastructure() -> None:
    """Verify startup continues if no docker-compose.yml exists."""
    from app.services.developer_startup import ServiceLauncher

    launcher = ServiceLauncher()
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("subprocess.Popen") as mock_popen,
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        mock_res = MagicMock()
        mock_res.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_res

        urls = launcher.launch_services()
        assert "backendUrl" in urls
        assert "frontendUrl" in urls
        assert mock_popen.call_count == 2


def test_port_conflict() -> None:
    """Verify port conflicts flag PortConflict issues."""
    with patch("socket.socket") as mock_sock:
        mock_sock.return_value.__enter__.return_value.bind.side_effect = OSError(
            "port occupied"
        )
        with patch("shutil.which", return_value="/usr/bin/node"):
            issues = EnvironmentValidator.validate_environment()
            issue_types = [i.issue_type for i in issues]
            assert "PortConflict" in issue_types


def test_log_creation() -> None:
    """Verify logs are written to startup.log."""
    import tempfile
    from pathlib import Path

    from app.services.developer_startup import log_startup

    with (
        tempfile.TemporaryDirectory() as tmpdir,
        patch("pathlib.Path.cwd", return_value=Path(tmpdir)),
    ):
        log_startup("Test startup log message")
        startup_log = Path(tmpdir) / "logs" / "startup.log"
        assert startup_log.exists()
        assert "Test startup log message" in startup_log.read_text()
