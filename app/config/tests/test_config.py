import threading
import time

import pytest

from app.config.exceptions import ConfigurationValidationException
from app.config.manager import ConfigurationManager
from app.config.profiles import RuntimeProfiles
from app.config.validator import ConfigurationValidator
from app.core.settings.config import settings


def test_configuration_manager_singleton() -> None:
    mgr1 = ConfigurationManager()
    mgr2 = ConfigurationManager()
    assert mgr1 is mgr2


def test_base_defaults_loading() -> None:
    manager = ConfigurationManager()
    # Reset manager config state for isolation
    manager._config = None
    manager._report = None

    config = manager.get_config()
    assert config.app.app_name == "SeedOpsLite"
    assert config.redis.redis_port == 6379
    assert config.logging.log_level == "debug"

    report = manager.get_report()
    assert report.statistics.loaded_sources_count >= 1
    assert report.statistics.active_profile == "development"


def test_programmatic_overrides() -> None:
    manager = ConfigurationManager()
    overrides = {
        "app": {"app_name": "TestAppName", "app_port": 9090},
        "redis": {"redis_host": "cache.test.internal"},
    }

    config = manager.reload(programmatic_overrides=overrides)
    assert config.app.app_name == "TestAppName"
    assert config.app.app_port == 9090
    assert config.redis.redis_host == "cache.test.internal"


def test_profile_resolution_and_overrides() -> None:
    # 1. Dev Profile
    overrides_dev = RuntimeProfiles.get_overrides("development")
    assert overrides_dev["app"]["app_env"] == "development"
    assert overrides_dev["app"]["app_debug"] is True

    # 2. Testing Profile
    overrides_test = RuntimeProfiles.get_overrides("testing")
    assert overrides_test["app"]["app_env"] == "testing"
    assert overrides_test["redis"]["redis_db"] == 9
    assert overrides_test["seeder"]["default_seed"] == 42

    # 3. Production Profile
    overrides_prod = RuntimeProfiles.get_overrides("production")
    assert overrides_prod["app"]["app_env"] == "production"
    assert overrides_prod["app"]["app_debug"] is False


def test_env_variables_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEEDOPS_APP_NAME", "EnvAppName")
    monkeypatch.setenv("SEEDOPS_REDIS_PORT", "1234")
    monkeypatch.setenv("SEEDOPS_APP_DEBUG", "false")
    monkeypatch.setenv("SEEDOPS_GEMINI_API_KEY", "secret_key")

    manager = ConfigurationManager()
    config = manager.reload(profile_overrides=False)

    assert config.app.app_name == "EnvAppName"
    assert config.redis.redis_port == 1234
    assert config.app.app_debug is False
    assert config.llm.gemini_api_key == "secret_key"


def test_schema_and_range_validations() -> None:
    validator = ConfigurationValidator()

    # 1. Schema failures (invalid types)
    bad_schema = {"app": {"app_port": "not_an_int"}}
    with pytest.raises(ConfigurationValidationException):
        validator.validate(bad_schema)

    # 2. Port range constraints
    bad_port = {"app": {"app_port": 99999}}
    with pytest.raises(ConfigurationValidationException):
        validator.validate(bad_port)

    # 3. Connections range constraints
    bad_conn = {"redis": {"redis_max_connections": 0}}
    with pytest.raises(ConfigurationValidationException):
        validator.validate(bad_conn)

    # 4. LLM retry constraints
    bad_retries = {"llm": {"max_retries": -5}}
    with pytest.raises(ConfigurationValidationException):
        validator.validate(bad_retries)


def test_production_profile_security_warnings() -> None:
    validator = ConfigurationValidator()

    # Production with debug enabled and empty Redis password
    prod_insecure = {
        "app": {"app_env": "production", "app_debug": True},
        "redis": {"redis_password": None},
    }
    _, warnings = validator.validate(prod_insecure)
    assert any("Debug mode is enabled" in w for w in warnings)
    assert any("Redis password is empty" in w for w in warnings)


def test_backward_compatibility_settings_sync() -> None:
    manager = ConfigurationManager()
    overrides = {
        "app": {"app_name": "LegacySyncApp", "app_env": "testing"},
        "llm": {"gemini_model": "test-gemini-model", "max_retries": 10},
    }

    # Load new config and verify global Pydantic Settings object synchronizes
    manager.reload(programmatic_overrides=overrides)

    assert settings.APP_NAME == "LegacySyncApp"
    assert settings.APP_ENV == "testing"
    assert settings.GEMINI_MODEL == "test-gemini-model"
    assert settings.LLM_MAX_RETRIES == 10


def test_flat_properties_equivalence() -> None:
    manager = ConfigurationManager()
    overrides = {
        "app": {"app_name": "EquivalenceApp", "app_env": "production"},
        "redis": {"redis_host": "equiv-host", "redis_port": 8888},
    }
    config = manager.reload(programmatic_overrides=overrides)

    assert config.APP_NAME == "EquivalenceApp"
    assert config.APP_ENV == "production"
    assert config.REDIS_HOST == "equiv-host"
    assert config.REDIS_PORT == 8888


def test_concurrent_reload_requests() -> None:
    manager = ConfigurationManager()
    errors = []

    def reload_worker(name: str, port: int) -> None:
        try:
            overrides = {"app": {"app_name": name, "app_port": port}}
            # Concurrent reload calls
            manager.reload(programmatic_overrides=overrides)
            # Verify atomic read
            config = manager.get_config()
            if config.app.app_name == "ThreadA":
                assert config.app.app_port == 1000
            elif config.app.app_name == "ThreadB":
                assert config.app.app_port == 2000
        except Exception as e:
            errors.append(e)

    threads = []
    t1 = threading.Thread(target=reload_worker, args=("ThreadA", 1000))
    t2 = threading.Thread(target=reload_worker, args=("ThreadB", 2000))
    threads.extend([t1, t2])

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent reload encountered errors: {errors}"


def test_atomic_configuration_commit() -> None:
    manager = ConfigurationManager()

    # Set initial state
    manager.reload(
        programmatic_overrides={"app": {"app_name": "InitialApp", "app_port": 8000}}
    )

    stop_event = threading.Event()
    read_errors = []

    def reader() -> None:
        while not stop_event.is_set():
            name = settings.APP_NAME
            port = settings.APP_PORT
            if (name == "InitialApp" and port != 8000) or (
                name == "UpdatedApp" and port != 9999
            ):
                read_errors.append(f"Inconsistent state: name={name}, port={port}")
            time.sleep(0.001)

    reader_thread = threading.Thread(target=reader)
    reader_thread.start()

    # Trigger updates
    for _ in range(20):
        manager.reload(
            programmatic_overrides={"app": {"app_name": "UpdatedApp", "app_port": 9999}}
        )
        time.sleep(0.005)
        manager.reload(
            programmatic_overrides={"app": {"app_name": "InitialApp", "app_port": 8000}}
        )
        time.sleep(0.005)

    stop_event.set()
    reader_thread.join()

    assert len(read_errors) == 0, f"Read errors found: {read_errors}"


def test_malformed_configuration_failure(tmp_path) -> None:
    config_file = tmp_path / "malformed.json"
    config_file.write_text("{invalid json", encoding="utf-8")

    manager = ConfigurationManager()
    with pytest.raises(ConfigurationValidationException) as exc_info:
        manager.reload(config_file_path=str(config_file))

    assert "Malformed configuration file" in str(exc_info.value)


def test_precedence_ordering(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        '{"app": {"app_debug": true}, "logging": {"log_level": "warning"}}',
        encoding="utf-8",
    )

    # Setup env
    monkeypatch.setenv("SEEDOPS_LOG_LEVEL", "warning")
    monkeypatch.setenv("SEEDOPS_APP_ENV", "production")

    manager = ConfigurationManager()
    # Load without programmatic overrides
    config = manager.reload(config_file_path=str(config_file))

    # app_debug should be False (Profile overrides File)
    assert config.app.app_debug is False
    # log_level should be "warning" (Environment overrides Profile)
    assert config.logging.log_level == "warning"

    # Load with programmatic overrides
    config = manager.reload(
        config_file_path=str(config_file),
        programmatic_overrides={"logging": {"log_level": "debug"}},
    )
    # log_level should be "debug" (Programmatic overrides Environment)
    assert config.logging.log_level == "debug"


def test_dynamic_type_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEEDOPS_APP_PORT", "9999")
    monkeypatch.setenv("SEEDOPS_APP_DEBUG", "true")
    monkeypatch.setenv("SEEDOPS_REDIS_TIMEOUT", "10")
    monkeypatch.setenv("SEEDOPS_WF_TIMEOUT", "45.5")
    monkeypatch.setenv("SEEDOPS_REDIS_PASSWORD", "some_password_value")

    manager = ConfigurationManager()
    config = manager.reload()

    assert config.app.app_port == 9999
    assert config.app.app_debug is True
    assert config.redis.redis_timeout_seconds == 10
    assert config.workflow.default_timeout == 45.5
    assert config.redis.redis_password == "some_password_value"  # noqa: S105


def test_deep_merge_isolation() -> None:
    manager = ConfigurationManager()
    manager.reload(programmatic_overrides={"app": {"app_env": "testing"}})

    overrides = {"redis": {"redis_host": "test-host"}}
    config1 = manager.reload(programmatic_overrides=overrides)
    config1.redis.redis_host = "mutated-host"

    config2 = manager.reload(programmatic_overrides={"app": {"app_env": "testing"}})
    overrides_test = RuntimeProfiles.get_overrides("testing")
    assert overrides_test.get("redis", {}).get("redis_db", 9) == 9
    assert config2.redis.redis_db == 9


def test_startup_integration() -> None:
    manager = ConfigurationManager()
    config = manager.get_config()
    assert config is not None
    assert config.app.app_name == settings.APP_NAME
