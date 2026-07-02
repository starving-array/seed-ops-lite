from collections.abc import Generator
from typing import Any

from app.platform.artifacts.interfaces import ArtifactProvider, DatasetStorageManager


class DiskArtifactProvider(ArtifactProvider):
    """Local disk-backed implementation of the ArtifactProvider interface."""

    async def write_file(self, file_path: str, data: bytes) -> str:
        raise NotImplementedError()

    async def read_file(self, file_path: str) -> bytes:
        raise NotImplementedError()

    async def delete_file(self, file_path: str) -> None:
        raise NotImplementedError()

    async def file_exists(self, file_path: str) -> bool:
        raise NotImplementedError()

    async def purge_directory(self, dir_path: str) -> None:
        raise NotImplementedError()


class DiskDatasetStorageManager(DatasetStorageManager):
    """Local disk and Parquet-backed implementation of the DatasetStorageManager interface."""

    async def write_table_dataset(
        self, workflow_id: str, table_name: str, records: list[dict[str, Any]]
    ) -> str:
        raise NotImplementedError()

    async def read_table_dataset_preview(
        self, workflow_id: str, table_name: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        raise NotImplementedError()

    def stream_table_dataset_csv(
        self, workflow_id: str, table_name: str, chunk_size_rows: int = 5000
    ) -> Generator[str, None, None]:
        raise NotImplementedError()

    def stream_multi_table_zip(
        self, workflow_id: str, tables: list[str] | None = None
    ) -> Generator[bytes, None, None]:
        raise NotImplementedError()

    async def get_dataset_metadata(self, workflow_id: str) -> dict[str, Any] | None:
        raise NotImplementedError()

    async def delete_dataset(self, workflow_id: str) -> None:
        raise NotImplementedError()

    async def verify_dataset_integrity(self, workflow_id: str) -> bool:
        raise NotImplementedError()
