from typing import Any

from pydantic import BaseModel, Field


class ColumnModel(BaseModel):
    id: str
    name: str
    type: str
    is_primary_key: bool = Field(alias="isPrimaryKey")
    is_nullable: bool = Field(alias="isNullable")
    default_value: str = Field(alias="defaultValue")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class TableModel(BaseModel):
    id: str
    name: str
    columns: list[ColumnModel]


class RelationshipModel(BaseModel):
    id: str
    name: str
    source_table_id: str = Field(alias="sourceTableId")
    source_column_id: str = Field(alias="sourceColumnId")
    target_table_id: str = Field(alias="targetTableId")
    target_column_id: str = Field(alias="targetColumnId")
    type: str
    is_required: bool = Field(alias="isRequired")
    cascade_delete: bool = Field(alias="cascadeDelete")
    cascade_update: bool = Field(alias="cascadeUpdate")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class SchemaModel(BaseModel):
    tables: list[TableModel]
    relationships: list[RelationshipModel]


class ValidationResultModel(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    description: str
    suggested_fix: str = Field(alias="suggestedFix")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class AISuggestionModel(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    explanation: str
    suggested_action: str | None = Field(default=None, alias="suggestedAction")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class AIAssistantResponse(BaseModel):
    status: str
    summary: str
    suggestions: list[AISuggestionModel]
    execution_duration_ms: float = Field(..., alias="executionDurationMs")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class GenerateRequestModel(BaseModel):
    schema_state: SchemaModel = Field(..., alias="schemaState")
    row_targets: dict[str, int] = Field(..., alias="rowTargets")
    seed: int | None = None
    batch_size: int = Field(default=100, alias="batchSize")
    output_format: str = Field(default="json", alias="outputFormat")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class TableProgressModel(BaseModel):
    table_name: str = Field(..., alias="tableName")
    status: str
    rows_generated: int = Field(..., alias="rowsGenerated")
    target_rows: int = Field(..., alias="targetRows")
    error: str | None = None

    class Config:
        populate_by_name = True
        populate_by_alias = True


class GenerateResponseModel(BaseModel):
    workflow_id: str = Field(..., alias="workflowId")
    status: str
    progress: list[TableProgressModel]
    total_rows_generated: int = Field(..., alias="totalRowsGenerated")
    duration_ms: float = Field(..., alias="durationMs")
    errors: list[str]
    download_placeholder: str | None = Field(default=None, alias="downloadPlaceholder")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class JobModel(BaseModel):
    job_id: str = Field(..., alias="jobId")
    type: str
    status: str
    started_at: str = Field(..., alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")
    duration: float = 0.0
    progress: float = 0.0
    owner: str = Field(default="admin", alias="owner")
    result_summary: str | None = Field(default=None, alias="resultSummary")
    error_message: str | None = Field(default=None, alias="errorMessage")
    details: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
        populate_by_alias = True


class ExportSettingsModel(BaseModel):
    workflow_id: str = Field(..., alias="workflowId")
    format: str
    tables: list[str] = Field(default_factory=list)
    single_file: bool = Field(default=True, alias="singleFile")
    compression: bool = Field(default=False, alias="compression")
    include_metadata: bool = Field(default=False, alias="includeMetadata")
    file_name_convention: str = Field(default="default", alias="fileNameConvention")

    class Config:
        populate_by_name = True
        populate_by_alias = True
