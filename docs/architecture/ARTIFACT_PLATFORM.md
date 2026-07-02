# SafeSeedOps Artifact Platform Baseline
**Lifecycle, Formats, and Streaming Designs**

---

## 1. Directory Structure

All generated Parquet table files and indexing manifests are isolated in unique directories relative to the dataset root folder:

```text
storage/datasets/
   └── dataset_{workflow_id}/
          ├── manifest.json         # Index metadata manifest
          ├── users.parquet         # PyArrow Parquet table
          └── orders.parquet        # PyArrow Parquet table
```

---

## 2. Manifest Schema Specification

Every generated dataset is accompanied by a `manifest.json` indexing file detailing structural and validation parameters:

```json
{
  "datasetId": "wf_123",
  "projectId": "default",
  "jobId": "wf_123",
  "schemaVersion": 1,
  "storageVersion": 1,
  "platformVersion": "1.0.0",
  "generatorVersion": "0.1.0",
  "createdAt": "2026-07-02T17:28:44.123456",
  "expiresAt": "2026-07-03T17:28:44.123456",
  "tables": [
    {
      "name": "users",
      "fileName": "users.parquet",
      "rowCount": 15,
      "checksum": "a3b9..."
    }
  ],
  "checksums": {
    "users.parquet": "a3b9..."
  },
  "rowCounts": {
    "users": 15
  },
  "datasetSize": 4512,
  "compression": "snappy"
}
```

---

## 3. Storage Flow

```text
[Synthetic Generator] ──> Record Batch ──> [PyArrow Table] ──> [DiskDatasetStorageManager]
                                                                        │
                                                                        ▼
                                                             Write snappy.parquet
                                                                        │
                                                                        ▼
                                                             Update manifest.json
```

---

## 4. Streaming Download Flow

Streaming downloads prevent memory bloating by converting Parquet row groups to CSV bytes on-the-fly:

```text
[Client GET /download]
         │
         ▼
[DiskDatasetStorageManager] ──> Open ParquetFile
                                       │
                                       ▼
                            Yield CSV Header chunk
                                       │
                                       ▼
                            Loop Row Groups ──> Convert to RecordBatch ──> Yield CSV rows
```

---

## 5. Checksum & Integrity Verification

1.  **Computation**: Before archiving or downloading, the actual SHA-256 of the table `.parquet` file is calculated.
2.  **Integrity Check**: The calculated checksum is verified against the entry inside `manifest.json`. If it does not match, a validation/integrity error is raised.
