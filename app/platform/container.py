from typing import Any

from app.core.lifecycle.container import container
from app.platform.artifacts.interfaces import ArtifactProvider, DatasetStorageManager
from app.platform.persistence.interfaces import PersistenceProvider
from app.platform.runtime.interfaces import RuntimeProvider


def register_platform_providers(
    persistence_factory: Any = None,
    runtime_factory: Any = None,
    artifact_factory: Any = None,
    dataset_factory: Any = None,
) -> None:
    """Utility helper to bind specific implementation factories to platform interface keys."""
    if persistence_factory:
        container.register(PersistenceProvider, persistence_factory)
    if runtime_factory:
        container.register(RuntimeProvider, runtime_factory)
    if artifact_factory:
        container.register(ArtifactProvider, artifact_factory)
    if dataset_factory:
        container.register(DatasetStorageManager, dataset_factory)


def get_persistence_provider() -> PersistenceProvider:
    """Retrieve the resolved active PersistenceProvider instance.

    Falls back to SQLitePersistenceProvider if the container has not been
    initialized (e.g., in test environments without lifespan).
    """
    try:
        return container.get(PersistenceProvider)
    except ValueError:
        from app.platform.providers.sqlite import SQLitePersistenceProvider

        return SQLitePersistenceProvider()


_runtime_manager_instance: RuntimeProvider | None = None


def get_runtime_provider() -> RuntimeProvider:
    """Retrieve the resolved active RuntimeProvider instance."""
    global _runtime_manager_instance  # noqa: PLW0603
    try:
        return container.get(RuntimeProvider)
    except ValueError:
        if _runtime_manager_instance is None:
            from app.platform.runtime.manager import RuntimeManager

            _runtime_manager_instance = RuntimeManager()
        return _runtime_manager_instance


def get_artifact_provider() -> ArtifactProvider:
    """Retrieve the resolved active ArtifactProvider instance."""
    try:
        return container.get(ArtifactProvider)
    except ValueError:
        from app.platform.providers.disk import DiskArtifactProvider

        return DiskArtifactProvider()


def get_dataset_storage_manager() -> DatasetStorageManager:
    """Retrieve the resolved active DatasetStorageManager instance."""
    try:
        return container.get(DatasetStorageManager)
    except ValueError:
        from app.platform.providers.disk import DiskDatasetStorageManager

        return DiskDatasetStorageManager()
