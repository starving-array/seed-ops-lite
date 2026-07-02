from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any


class ArtifactProvider(ABC):
    """Abstract interface defining read/write and management operations for files and export packages."""

    @abstractmethod
    async def write_file(self, file_path: str, data: bytes) -> str:
        """Write binary data payload to target storage and return file URI."""
        pass

    @abstractmethod
    async def read_file(self, file_path: str) -> bytes:
        """Read binary contents of a file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> None:
        """Delete a file from the workspace filesystem."""
        pass

    @abstractmethod
    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in the storage provider path."""
        pass

    @abstractmethod
    async def purge_directory(self, dir_path: str) -> None:
        """Purge all files inside a directory (e.g. for retention cleanups)."""
        pass


class DatasetStorageManager(ABC):
    """Abstract interface defining the Parquet serialization, indexing, and streaming pipeline."""

    @abstractmethod
    async def write_table_dataset(
        self, workflow_id: str, table_name: str, records: list[dict[str, Any]]
    ) -> str:
        """Serialize a block of mock records to a Parquet file and update index metadata."""
        pass

    @abstractmethod
    async def read_table_dataset_preview(
        self, workflow_id: str, table_name: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retrieve a small slice of records for UI preview portals."""
        pass

    @abstractmethod
    def stream_table_dataset_csv(
        self, workflow_id: str, table_name: str, chunk_size_rows: int = 5000
    ) -> Generator[str, None, None]:
        """Stream a table's dataset rows chunk-by-chunk formatting them as CSV strings."""
        pass

    @abstractmethod
    def stream_multi_table_zip(
        self, workflow_id: str, tables: list[str] | None = None
    ) -> Generator[bytes, None, None]:
        """Stream a compressed ZIP buffer containing individual table CSV files and README metadata."""
        pass

    @abstractmethod
    async def get_dataset_metadata(self, workflow_id: str) -> dict[str, Any] | None:
        """Fetch index metadata (row counts, checksums) for a generated dataset."""
        pass

    @abstractmethod
    async def delete_dataset(self, workflow_id: str) -> None:
        """Delete all Parquet files and metadata indexes associated with a dataset run."""
        pass

    @abstractmethod
    async def verify_dataset_integrity(self, workflow_id: str) -> bool:
        """Verify checksums and record metrics inside a dataset's metadata file."""
        pass

    @abstractmethod
    def get_dataset_storage_path(self, workflow_id: str) -> str:
        """Return the canonical storage path string for the dataset identified by workflow_id.

        This is an opaque metadata label (str, not Path) that callers may record in
        SQLite or log for auditability. Implementations are free to return a filesystem
        path, a URI, or any other stable identifier — callers must not assume filesystem
        semantics on the returned value.
        """
        pass
