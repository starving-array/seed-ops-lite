import contextlib
import csv
import datetime
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from app.core.logging.logging import logger
from app.core.version import APP_VERSION
from app.platform.artifacts.interfaces import ArtifactProvider, DatasetStorageManager
from app.platform.configuration.settings import platform_settings
from app.platform.persistence.exceptions import EntityNotFoundError, PersistenceError
from app.platform.persistence.resolver import ProjectResolver
from app.telemetry.events import EventID


class DiskArtifactProvider(ArtifactProvider):
    """Local disk-backed implementation of the ArtifactProvider interface."""

    def __init__(self, base_dir: str = "storage") -> None:
        self.base_dir = Path(base_dir).resolve()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.base_dir / p).resolve()

    async def write_file(self, file_path: str, data: bytes) -> str:
        try:
            target = self._resolve(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return str(target)
        except Exception as e:
            raise PersistenceError(f"Failed to write file artifact: {e}") from e

    async def read_file(self, file_path: str) -> bytes:
        target = self._resolve(file_path)
        if not target.exists():
            raise EntityNotFoundError(f"Artifact file not found: {file_path}")
        try:
            return target.read_bytes()
        except Exception as e:
            raise PersistenceError(f"Failed to read file artifact: {e}") from e

    async def delete_file(self, file_path: str) -> None:
        try:
            target = self._resolve(file_path)
            if target.exists():
                target.unlink()
        except Exception as e:
            raise PersistenceError(f"Failed to delete file artifact: {e}") from e

    async def file_exists(self, file_path: str) -> bool:
        target = self._resolve(file_path)
        return target.exists()

    async def purge_directory(self, dir_path: str) -> None:
        try:
            target = self._resolve(dir_path)
            if target.exists() and target.is_dir():
                shutil.rmtree(target)
        except Exception as e:
            raise PersistenceError(f"Failed to purge directory: {e}") from e


class DiskDatasetStorageManager(DatasetStorageManager):
    """Local disk and Parquet-backed implementation of the DatasetStorageManager interface."""

    def __init__(self) -> None:
        self.datasets_dir = Path(platform_settings.DATASETS_DIR).resolve()

    def _get_dataset_dir(self, workflow_id: str) -> Path:
        return self.datasets_dir / f"dataset_{workflow_id}"

    def get_dataset_storage_path(self, workflow_id: str) -> str:
        """Return the canonical storage path string for this dataset.

        Implements DatasetStorageManager.get_dataset_storage_path. Delegates to the
        private _get_dataset_dir helper and converts to str so callers receive an
        opaque label rather than a filesystem handle.
        """
        return str(self._get_dataset_dir(workflow_id))

    def _compute_sha256(self, filepath: Path) -> str:
        h = hashlib.sha256()
        with filepath.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    async def write_table_dataset(
        self, workflow_id: str, table_name: str, records: list[dict[str, Any]]
    ) -> str:
        try:
            dataset_dir = self._get_dataset_dir(workflow_id)
            dataset_dir.mkdir(parents=True, exist_ok=True)

            file_path = dataset_dir / f"{table_name}.parquet"

            # Serialize using PyArrow Parquet
            table = pa.Table.from_pylist(records)
            pq.write_table(table, file_path)  # type: ignore[no-untyped-call]

            checksum = self._compute_sha256(file_path)
            file_size = file_path.stat().st_size

            # Load or initialize manifest
            manifest_path = dataset_dir / "manifest.json"
            manifest: dict[str, Any] = {}
            if manifest_path.exists():
                with manifest_path.open("r") as f, contextlib.suppress(Exception):
                    manifest = json.load(f)

            if not manifest:
                created_at = datetime.datetime.utcnow()
                expires_at = created_at + datetime.timedelta(
                    hours=platform_settings.DATASET_RETENTION_HOURS
                )
                manifest = {
                    "datasetId": workflow_id,
                    "projectId": ProjectResolver.get_active_project_id(),
                    "jobId": workflow_id,
                    "schemaVersion": 1,
                    "storageVersion": 1,
                    "platformVersion": "1.0.0",
                    "generatorVersion": APP_VERSION,
                    "createdAt": created_at.isoformat(),
                    "expiresAt": expires_at.isoformat(),
                    "tables": [],
                    "checksums": {},
                    "rowCounts": {},
                    "datasetSize": 0,
                    "compression": "snappy",
                }

            # Update tables info
            tables_list = manifest.get("tables", [])
            # Remove duplicate entry if exists
            tables_list = [t for t in tables_list if t.get("name") != table_name]
            tables_list.append(
                {
                    "name": table_name,
                    "fileName": f"{table_name}.parquet",
                    "rowCount": len(records),
                    "checksum": checksum,
                }
            )
            manifest["tables"] = tables_list
            manifest["checksums"][f"{table_name}.parquet"] = checksum
            manifest["rowCounts"][table_name] = len(records)

            # Compute total dataset size
            total_size = sum(
                (dataset_dir / t["fileName"]).stat().st_size
                for t in tables_list
                if (dataset_dir / t["fileName"]).exists()
            )
            manifest["datasetSize"] = total_size

            with manifest_path.open("w") as f:
                json.dump(manifest, f, indent=2)

            logger.info(
                EventID.LOG_INFO,
                f"Wrote table dataset {table_name} for run {workflow_id}.",
                details={
                    "workflow_id": workflow_id,
                    "table": table_name,
                    "rows": len(records),
                    "size_bytes": file_size,
                },
            )

            return str(file_path)
        except Exception as e:
            raise PersistenceError(f"Failed to write table dataset: {e}") from e

    async def read_table_dataset_preview(
        self, workflow_id: str, table_name: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        dataset_dir = self._get_dataset_dir(workflow_id)
        file_path = dataset_dir / f"{table_name}.parquet"
        if not file_path.exists():
            raise EntityNotFoundError(
                f"Dataset table file not found: {workflow_id}/{table_name}"
            )
        try:
            table = pq.read_table(file_path)  # type: ignore[no-untyped-call]
            sliced = table.slice(0, min(limit, table.num_rows))
            return sliced.to_pylist()  # type: ignore[no-any-return]
        except Exception as e:
            raise PersistenceError(f"Failed to read dataset preview: {e}") from e

    def stream_table_dataset_csv(
        self, workflow_id: str, table_name: str, chunk_size_rows: int = 5000
    ) -> Generator[str, None, None]:
        dataset_dir = self._get_dataset_dir(workflow_id)
        file_path = dataset_dir / f"{table_name}.parquet"
        if not file_path.exists():
            raise EntityNotFoundError(
                f"Dataset table file not found: {workflow_id}/{table_name}"
            )
        try:
            pf = pq.ParquetFile(file_path)  # type: ignore[no-untyped-call]
            schema = pf.schema_arrow
            field_names = schema.names

            # 1. Output Header
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(field_names)
            yield output.getvalue()

            # 2. Iterate row groups in batches
            for i in range(pf.num_row_groups):
                rg = pf.read_row_group(i)  # type: ignore[no-untyped-call]
                batches = rg.to_batches(max_chunksize=chunk_size_rows)
                for batch in batches:
                    output = io.StringIO()
                    writer = csv.writer(output)
                    pydict = batch.to_pydict()
                    num_rows = batch.num_rows
                    for row_idx in range(num_rows):
                        row = [pydict[col][row_idx] for col in field_names]
                        writer.writerow(row)
                    yield output.getvalue()
        except Exception as e:
            raise PersistenceError(f"Failed to stream dataset CSV: {e}") from e

    def stream_multi_table_zip(
        self, workflow_id: str, tables: list[str] | None = None
    ) -> Generator[bytes, None, None]:
        dataset_dir = self._get_dataset_dir(workflow_id)
        manifest_path = dataset_dir / "manifest.json"
        if not manifest_path.exists():
            raise EntityNotFoundError(
                f"Dataset manifest not found for run {workflow_id}"
            )

        try:
            with manifest_path.open("r") as f:
                manifest_data = json.load(f)

            if tables is None:
                tables = [t["name"] for t in manifest_data.get("tables", [])]

            temp_dir = Path("storage/temp_exports")
            temp_dir.mkdir(parents=True, exist_ok=True)

            fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", dir=str(temp_dir))
            os.close(fd)

            try:
                with zipfile.ZipFile(
                    temp_zip_path, "w", zipfile.ZIP_DEFLATED
                ) as zip_file:
                    # Write manifest.json
                    zip_file.write(manifest_path, "manifest.json")

                    # Write README.md
                    readme = (
                        f"# SafeSeedOps Synthetic Dataset Package\n\n"
                        f"Dataset ID: {workflow_id}\n"
                        f"Project ID: {manifest_data.get('projectId', 'default')}\n"
                        f"Created At: {manifest_data.get('createdAt')}\n"
                        f"Tables included: {', '.join(tables)}\n"
                    )
                    zip_file.writestr("README.md", readme)

                    # Export tables inside zip
                    for table_name in tables:
                        parquet_file = dataset_dir / f"{table_name}.parquet"
                        if not parquet_file.exists():
                            continue

                        with zip_file.open(f"{table_name}.csv", "w") as csv_entry:
                            pf = pq.ParquetFile(parquet_file)  # type: ignore[no-untyped-call]
                            schema = pf.schema_arrow
                            field_names = schema.names

                            # Header
                            header_line = ",".join(field_names) + "\n"
                            csv_entry.write(header_line.encode("utf-8"))

                            # Content
                            for i in range(pf.num_row_groups):
                                rg = pf.read_row_group(i)  # type: ignore[no-untyped-call]
                                batches = rg.to_batches(max_chunksize=5000)
                                for batch in batches:
                                    output = io.StringIO()
                                    writer = csv.writer(output)
                                    pydict = batch.to_pydict()
                                    num_rows = batch.num_rows
                                    for row_idx in range(num_rows):
                                        row = [
                                            pydict[col][row_idx] for col in field_names
                                        ]
                                        writer.writerow(row)
                                    csv_entry.write(output.getvalue().encode("utf-8"))

                # Stream the zipped file
                with Path(temp_zip_path).open("rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        yield chunk

            finally:
                with contextlib.suppress(Exception):
                    Path(temp_zip_path).unlink()
        except Exception as e:
            raise PersistenceError(f"Failed to stream ZIP package: {e}") from e

    async def get_dataset_metadata(self, workflow_id: str) -> dict[str, Any] | None:
        dataset_dir = self._get_dataset_dir(workflow_id)
        manifest_path = dataset_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            with manifest_path.open("r") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception as e:
            raise PersistenceError(f"Failed to read dataset metadata: {e}") from e

    async def delete_dataset(self, workflow_id: str) -> None:
        try:
            dataset_dir = self._get_dataset_dir(workflow_id)
            if dataset_dir.exists() and dataset_dir.is_dir():
                shutil.rmtree(dataset_dir)
        except Exception as e:
            raise PersistenceError(f"Failed to delete dataset run: {e}") from e

    async def verify_dataset_integrity(self, workflow_id: str) -> bool:
        dataset_dir = self._get_dataset_dir(workflow_id)
        manifest_path = dataset_dir / "manifest.json"
        if not manifest_path.exists():
            return False
        try:
            with manifest_path.open("r") as f:
                manifest_data = json.load(f)

            for t in manifest_data.get("tables", []):
                table_file = dataset_dir / t["fileName"]
                if not table_file.exists():
                    return False
                actual_checksum = self._compute_sha256(table_file)
                if actual_checksum != t.get("checksum"):
                    return False
            return True
        except Exception:
            return False
