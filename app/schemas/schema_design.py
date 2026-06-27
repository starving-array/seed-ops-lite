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

