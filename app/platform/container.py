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
    """Retrieve the resolved active PersistenceProvider instance."""
    return container.get(PersistenceProvider)


def get_runtime_provider() -> RuntimeProvider:
    """Retrieve the resolved active RuntimeProvider instance."""
    return container.get(RuntimeProvider)


def get_artifact_provider() -> ArtifactProvider:
    """Retrieve the resolved active ArtifactProvider instance."""
    return container.get(ArtifactProvider)


def get_dataset_storage_manager() -> DatasetStorageManager:
    """Retrieve the resolved active DatasetStorageManager instance."""
    return container.get(DatasetStorageManager)
