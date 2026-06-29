# API Validation Specification — SafeSeedOps Lite

This document records the API contract validation, request/response models, validations, and test results for every FastAPI endpoint exposed by the backend.

---

## 1. System Health Endpoint

### `GET /health`
*   **Method**: `GET`
*   **Endpoint**: `/health`
*   **Request Model**: None
*   **Response Model**: `HealthResponse`
*   **Dependencies**: `redis_manager` health check.
*   **Frontend Usage**: Connectivity check during application bootstrap.
*   **Success Scenario**:
    *   *Condition*: Redis is running and connected.
    *   *HTTP Status*: `200 OK`
    *   *Payload*:
        ```json
        {
          "status": "healthy",
          "version": "0.1.0",
          "environment": "development",
          "uptime": 12.34,
          "python_version": "3.13.1",
          "redis_status": "healthy",
          "startup_time": "2026-06-29T14:00:00Z",
          "services": {
            "redis": {
              "status": "healthy",
              "details": null
            }
          }
        }
        ```
*   **Error Scenario**:
    *   *Condition*: Redis host is offline or connection times out.
    *   *HTTP Status*: `503 Service Unavailable`
    *   *Payload*: Same schema as success but with `status="unhealthy"`, `redis_status="unhealthy"`, and `details="Connection failed or timed out"`.
*   **Validation Status**: **PASS**

---

## 2. Schema Assistant Endpoints

### `GET /schema`
*   **Method**: `GET`
*   **Endpoint**: `/schema`
*   **Request Model**: None
*   **Response Model**: `SchemaModel`
*   **Dependencies**: Redis
*   **Frontend Usage**: Fetches the saved schema canvas design on designer startup.
*   **Success Scenario**:
    *   *Condition*: Saves are present in Redis. Returns saved state. If empty, returns a default schema configuration (containing two pre-configured tables: `users` and `orders` linked by a foreign key).
    *   *HTTP Status*: `200 OK`
*   **Error Scenario**:
    *   *Condition*: Redis is offline.
    *   *HTTP Status*: `500 Internal Server Error`
*   **Validation Status**: **PASS**

### `POST /schema`
*   **Method**: `POST`
*   **Endpoint**: `/schema`
*   **Request Model**: `SchemaModel` (JSON body containing tables and relationships list)
*   **Response Model**: `dict[str, str]` (e.g. `{"status": "success", "message": "Schema saved successfully"}`)
*   **Dependencies**: Redis
*   **Frontend Usage**: Click "Save Schema" button in Schema Designer.
*   **Success Scenario**:
    *   *Condition*: Valid SchemaModel schema details sent. Saves to Redis `schema_designer:state`.
    *   *HTTP Status*: `200 OK`
*   **Validation Scenario**:
    *   *Condition*: Body contains invalid schema formats (e.g., table missing `name` field).
    *   *HTTP Status*: `422 Unprocessable Entity` (Pydantic validation error)
*   **Validation Status**: **PASS**

### `POST /schema/validate`
*   **Method**: `POST`
*   **Endpoint**: `/schema/validate`
*   **Request Model**: `SchemaModel`
*   **Response Model**: `list[ValidationResultModel]`
*   **Dependencies**: None
*   **Frontend Usage**: Loaded in Schema Validation panel to show syntax and constraint errors.
*   **Success Scenario**:
    *   *Condition*: Schema design contains no errors. Returns compilation success details for each validation rule category (`severity="Passed"`).
    *   *HTTP Status*: `200 OK`
*   **Validation Scenario**:
    *   *Condition*: Schema has invalid identifiers, duplicate keys, or broken foreign references.
    *   *HTTP Status*: `200 OK` (returns list containing items with `severity="Error"` or `severity="Warning"`).
*   **Validation Status**: **PASS**

### `POST /schema/ai-assist`
*   **Method**: `POST`
*   **Endpoint**: `/schema/ai-assist`
*   **Request Model**: `SchemaModel`
*   **Response Model**: `AIAssistantResponse`
*   **Dependencies**: `SchemaValidationAgent`, Gemini API Key (`GEMINI_API_KEY`)
*   **Frontend Usage**: Click "Ask AI Assistant" in Schema Validation workspace.
*   **Success Scenario**:
    *   *Condition*: Valid `GEMINI_API_KEY` is present. Returns list of suggestions (Naming, Performance, Relationships, Best Practices) categorized by severity.
    *   *HTTP Status*: `200 OK`
*   **Error Scenario**:
    *   *Condition*: Gemini API Key is missing or invalid.
    *   *HTTP Status*: `200 OK` (Gracefully caught: returns status `"Failed"` and summary `"AI Schema Assistant is currently unavailable: Gemini API key is not configured."`).
*   **Validation Status**: **WARNING** (Functional but requires Gemini API Key setup in `.env`)

---

## 3. Data Generation Endpoints

### `POST /schema/generate`
*   **Method**: `POST`
*   **Endpoint**: `/schema/generate`
*   **Request Model**: `GenerateRequestModel` (schemaState, rowTargets, seed, batchSize, outputFormat)
*   **Response Model**: `GenerateResponseModel`
*   **Dependencies**: Redis, BackgroundTasks, `HybridSeeder`
*   **Frontend Usage**: Click "Start Generation" button.
*   **Success Scenario**:
    *   *Condition*: Valid generation payload. Queues task, sets status to `Queued`, and returns `workflowId`.
    *   *HTTP Status*: `200 OK`
*   **Validation Status**: **PASS**

### `GET /schema/generate/{workflowId}`
*   **Method**: `GET`
*   **Endpoint**: `/schema/generate/{workflowId}`
*   **Request Model**: None
*   **Response Model**: `GenerateResponseModel`
*   **Dependencies**: Redis
*   **Frontend Usage**: Polling generation progress.
*   **Success Scenario**:
    *   *Condition*: Generation exists in Redis. Returns status (`Running`, `Completed`, `Failed`) and progress arrays.
    *   *HTTP Status*: `200 OK`
*   **Error Scenario**:
    *   *Condition*: Session does not exist.
    *   *HTTP Status*: `404 Not Found`
*   **Validation Status**: **PASS**

### `POST /schema/generate/{workflowId}/cancel`
*   **Method**: `POST`
*   **Endpoint**: `/schema/generate/{workflowId}/cancel`
*   **Request Model**: None
*   **Response Model**: `dict[str, str]` (cancellation message)
*   **Dependencies**: Redis
*   **Frontend Usage**: Click "Cancel" on running job.
*   **Success Scenario**:
    *   *Condition*: Active workflow exists. Sets cancel flag.
    *   *HTTP Status*: `200 OK`
*   **Validation Status**: **PASS**

### `GET /schema/generate/{workflowId}/download`
*   **Method**: `GET`
*   **Endpoint**: `/schema/generate/{workflowId}/download`
*   **Request Model**: None
*   **Response Model**: `dict[str, Any]` (JSON statistics of generated rows)
*   **Dependencies**: Redis
*   **Frontend Usage**: Direct statistics check after generation finishes.
*   **Success Scenario**:
    *   *Condition*: Completed generation session. Returns row counts and format details.
    *   *HTTP Status*: `200 OK`
*   **Validation Status**: **PASS**

---

## 4. Operation Audit Log (Jobs)

### `GET /schema/jobs`
*   **Method**: `GET`
*   **Endpoint**: `/schema/jobs`
*   **Request Model**: None (optional query parameters: `status`, `job_type`, `search`)
*   **Response Model**: `list[JobModel]`
*   **Dependencies**: Redis
*   **Frontend Usage**: Job History dashboard tab list.
*   **Success Scenario**:
    *   *Condition*: Fetches and filters job histories sorted by startup timestamp descending.
    *   *HTTP Status*: `200 OK`
*   **Validation Status**: **PASS**

### `GET /schema/jobs/{job_id}`
*   **Method**: `GET`
*   **Endpoint**: `/schema/jobs/{job_id}`
*   **Request Model**: None
*   **Response Model**: `JobModel`
*   **Dependencies**: Redis
*   **Frontend Usage**: Clicking a job in the list to view errors or execution statistics.
*   **Success Scenario**:
    *   *Condition*: Job details exist in Redis.
    *   *HTTP Status*: `200 OK`
*   **Error Scenario**:
    *   *Condition*: Job ID is not found.
    *   *HTTP Status*: `404 Not Found`
*   **Validation Status**: **PASS**

### `POST /schema/jobs/{job_id}/cancel`
*   **Method**: `POST`
*   **Endpoint**: `/schema/jobs/{job_id}/cancel`
*   **Request Model**: None
*   **Response Model**: `dict[str, str]`
*   **Dependencies**: Redis
*   **Frontend Usage**: Cancel job button in Job History list.
*   **Success Scenario**:
    *   *Condition*: Running job exists. Cancels background generation/export loop.
    *   *HTTP Status*: `200 OK`
*   **Validation Status**: **PASS**

---

## 5. Exporter Workspace Endpoints

### `GET /schema/export/datasets`
*   **Method**: `GET`
*   **Endpoint**: `/schema/export/datasets`
*   **Request Model**: None
*   **Response Model**: `list[dict[str, Any]]`
*   **Dependencies**: Redis
*   **Frontend Usage**: Populates dropdown list of completed generation runs.
*   **Success Scenario**:
    *   *Condition*: Returns completed workflow runs.
    *   *HTTP Status*: `200 OK`
*   **Validation Status**: **PASS**

### `POST /schema/export`
*   **Method**: `POST`
*   **Endpoint**: `/schema/export`
*   **Request Model**: `ExportSettingsModel` (workflowId, format, tables, singleFile, compression, includeMetadata, fileNameConvention)
*   **Response Model**: `JobModel`
*   **Dependencies**: Redis, BackgroundTasks, `ExportEngine`
*   **Frontend Usage**: Initiate export format serialization.
*   **Success Scenario**:
    *   *Condition*: Valid target workflow ID and export settings. Starts background export loop.
    *   *HTTP Status*: `200 OK`
*   **Validation Status**: **PASS**

### `GET /schema/export/{export_job_id}/download`
*   **Method**: `GET`
*   **Endpoint**: `/schema/export/{export_job_id}/download`
*   **Request Model**: None
*   **Response Model**: `Response` (Binary stream)
*   **Dependencies**: Redis
*   **Frontend Usage**: Direct file attachment downloads.
*   **Success Scenario**:
    *   *Condition*: Export payload is compiled. Streams file content using custom media-type and disposition headers.
    *   *HTTP Status*: `200 OK`
*   **Error Scenario**:
    *   *Condition*: Missing export ID payload.
    *   *HTTP Status*: `404 Not Found`
*   **Validation Status**: **PASS**
