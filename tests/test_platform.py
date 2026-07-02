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


def test_disk_artifact_provider() -> None:
    """Test LocalDiskArtifactProvider write, read, file_exists, and delete functionality."""
    import shutil
    import tempfile

    from app.platform.providers.disk import DiskArtifactProvider

    temp_dir = tempfile.mkdtemp()
    try:
        provider = DiskArtifactProvider(base_dir=temp_dir)

        # Test write and exists
        import asyncio

        loop = asyncio.get_event_loop()

        async def run_test():
            file_uri = await provider.write_file("test.txt", b"Hello Artifact")
            assert file_uri is not None
            assert await provider.file_exists("test.txt") is True

            # Test read
            content = await provider.read_file("test.txt")
            assert content == b"Hello Artifact"

            # Test delete
            await provider.delete_file("test.txt")
            assert await provider.file_exists("test.txt") is False

        loop.run_until_complete(run_test())
    finally:
        shutil.rmtree(temp_dir)


def test_disk_dataset_storage_manager() -> None:
    """Test DiskDatasetStorageManager dataset creation, manifest, zip streaming, and integrity verification."""
    import asyncio
    import shutil
    import tempfile
    from unittest.mock import patch

    from app.platform.providers.disk import DiskDatasetStorageManager

    temp_dir = tempfile.mkdtemp()

    # Override PlatformSettings DATASETS_DIR to use temp folder
    with patch(
        "app.platform.configuration.settings.platform_settings.DATASETS_DIR", temp_dir
    ):
        manager = DiskDatasetStorageManager()
        loop = asyncio.get_event_loop()

        async def run_test():
            records = [{"id": i, "name": f"User {i}"} for i in range(15)]

            # 1. Write table dataset
            file_path = await manager.write_table_dataset("wf_123", "users", records)
            assert file_path is not None
            assert "users.parquet" in file_path

            # 2. Get and verify manifest
            manifest = await manager.get_dataset_metadata("wf_123")
            assert manifest is not None
            assert manifest["datasetId"] == "wf_123"
            assert "users" in manifest["rowCounts"]
            assert manifest["rowCounts"]["users"] == 15

            # 3. Read dataset preview
            preview = await manager.read_table_dataset_preview(
                "wf_123", "users", limit=5
            )
            assert len(preview) == 5
            assert preview[0]["id"] == 0

            # 4. Stream table dataset CSV
            csv_chunks = list(
                manager.stream_table_dataset_csv("wf_123", "users", chunk_size_rows=5)
            )
            assert len(csv_chunks) > 0
            full_csv = "".join(csv_chunks)
            assert "id,name" in full_csv

            # 5. Stream multi-table ZIP package
            zip_chunks = list(
                manager.stream_multi_table_zip("wf_123", tables=["users"])
            )
            assert len(zip_chunks) > 0
            full_zip = b"".join(zip_chunks)
            assert b"PK" in full_zip  # ZIP header identifier

            # 6. Verify integrity
            assert await manager.verify_dataset_integrity("wf_123") is True

            # 7. Delete dataset
            await manager.delete_dataset("wf_123")
            assert await manager.get_dataset_metadata("wf_123") is None

        loop.run_until_complete(run_test())
        shutil.rmtree(temp_dir)
