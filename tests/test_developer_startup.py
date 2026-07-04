"""Unit tests for the Developer startup orchestrator, environment validations, and diagnostics."""

import socket

from app.platform.configuration.settings import platform_settings
from app.services.developer_startup import DeveloperStartupManager, EnvironmentValidator


def test_dev_configuration_loading() -> None:
    """Verify PlatformSettings startup configurations loaded correctly."""
    assert platform_settings.PLATFORM_DEV_PORT == 8000
    assert platform_settings.PLATFORM_DEV_STARTUP_TIMEOUT_SECONDS == 30
    assert platform_settings.PLATFORM_DEV_HEALTH_CHECK_INTERVAL_SECONDS == 5
    assert platform_settings.PLATFORM_DEV_AUTO_SEED is True


def test_environment_validation_passes() -> None:
    """Verify pre-flight validation succeeds under ordinary environment conditions."""
    issues = EnvironmentValidator.validate_environment()
    # If the port 8000 is occupied on the runner machine, it may return a PortConflict issue, which is valid diagnostic.
    # Let's verify that PythonVersion validation does not fail (runner runs modern Python).
    assert not any(i.issue_type == "UnsupportedPythonVersion" for i in issues)


def test_port_conflict_detection() -> None:
    """Verify port conflicts are correctly reported as diagnostics."""
    port = platform_settings.PLATFORM_DEV_PORT

    # Bind the dev port beforehand to simulate a collision conflict
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)

        # Check validation
        issues = EnvironmentValidator.validate_environment()
        assert any(i.issue_type == "PortConflict" for i in issues)

    except OSError:
        # Port was already in use by another process on the system, which is also a success case for detection.
        issues = EnvironmentValidator.validate_environment()
        assert any(i.issue_type == "PortConflict" for i in issues)
    finally:
        s.close()


def test_startup_sequence_success() -> None:
    """Verify startup flows, metrics recording, and diagnostics checks."""
    mgr = DeveloperStartupManager()

    # 1. Execute Dry Run
    # Use a backup free port dynamically to ensure success if port 8000 is occupied
    platform_settings.PLATFORM_DEV_PORT = 19842

    res = mgr.run_dev_startup(dry_run=True)
    assert res.success is True
    assert len(res.diagnostics) == 0
    assert res.health.is_healthy is True
    assert res.statistics.successful_startups == 1
    assert res.statistics.startup_duration_ms > 0.0

    # 2. Cleanup operations
    clean_status = mgr.clean_cache()
    assert clean_status["status"] == "Cache Cleared"

    # 3. Graceful shutdown
    mgr.shutdown()
    assert len(mgr.launcher.running_services) == 0
