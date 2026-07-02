"""Unit tests for Platform Foundation packages, settings, and DI container bindings."""

from unittest.mock import MagicMock

from app.platform.artifacts.interfaces import ArtifactProvider, DatasetStorageManager
from app.platform.configuration.settings import PlatformSettings, platform_settings
from app.platform.container import (
    get_artifact_provider,
    get_dataset_storage_manager,
    get_persistence_provider,
    get_runtime_provider,
    register_platform_providers,
)
from app.platform.persistence.interfaces import PersistenceProvider
from app.platform.runtime.interfaces import RuntimeProvider


def test_platform_settings_loading() -> None:
    """Test that platform configuration settings load with correct defaults."""
    assert platform_settings.SQLITE_DB_PATH == "storage/database.sqlite"
    assert platform_settings.DATASETS_DIR == "storage/datasets"
    assert platform_settings.DATASET_RETENTION_HOURS == 24
    assert platform_settings.PERSISTENCE_PROVIDER == "sqlite"


def test_platform_settings_overrides() -> None:
    """Test setting customizations using constructor overrides."""
    custom = PlatformSettings(
        SQLITE_DB_PATH="test_db.sqlite",
        DATASET_RETENTION_HOURS=12,
    )
    assert custom.SQLITE_DB_PATH == "test_db.sqlite"
    assert custom.DATASET_RETENTION_HOURS == 12


def test_dependency_injection_bindings() -> None:
    """Test DI container registration and resolving of platform providers."""
    # Define simple mock implementations
    mock_persistence = MagicMock(spec=PersistenceProvider)
    mock_runtime = MagicMock(spec=RuntimeProvider)
    mock_artifact = MagicMock(spec=ArtifactProvider)
    mock_dataset = MagicMock(spec=DatasetStorageManager)

    # Register them
    register_platform_providers(
        persistence_factory=lambda: mock_persistence,
        runtime_factory=lambda: mock_runtime,
        artifact_factory=lambda: mock_artifact,
        dataset_factory=lambda: mock_dataset,
    )

    # Resolve and assert they match mocks
    assert get_persistence_provider() is mock_persistence
    assert get_runtime_provider() is mock_runtime
    assert get_artifact_provider() is mock_artifact
    assert get_dataset_storage_manager() is mock_dataset
