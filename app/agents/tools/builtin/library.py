# ruff: noqa: ARG002
import re
import time
from typing import Any

from app.agents.memory.manager import AgentMemoryManager
from app.agents.memory.models import MemoryQuery
from app.agents.tools.interface import Tool
from app.agents.tools.models import (
    ToolCapability,
    ToolCategory,
    ToolContext,
    ToolMetadata,
    ToolPermission,
    ToolRequest,
    ToolResponse,
)
from app.platform.configuration.settings import platform_settings
from app.platform.container import get_persistence_provider


class WorkflowStatusTool(Tool):
    """Retrieves current execution status or historical record of a workflow."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "workflow_id" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        wf_id = request.inputs["workflow_id"]
        try:
            pers = get_persistence_provider()
            # Try loading execution or jobs status
            job = await pers.get_job(wf_id)
            if job:
                return ToolResponse(
                    success=True,
                    outputs={"status": job.get("status"), "details": job},
                    duration=time.perf_counter() - start_time,
                )
            return ToolResponse(
                success=False,
                errors=[f"Workflow execution with ID '{wf_id}' not found."],
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Database status lookup failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="workflow-status",
            name="Workflow Status Lookup Tool",
            version="1.0.0",
            description="Fetch execution state and status details for a workflow run.",
            category=ToolCategory.WORKFLOW,
            capabilities=[ToolCapability.UTILITY_RUN],
            permissions_required=[ToolPermission.READ],
        )


class WorkflowExecutionTool(Tool):
    """Triggers or schedules a workflow execution run."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "workflow_id" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        wf_id = request.inputs["workflow_id"]
        try:
            pers = get_persistence_provider()
            await pers.create_job(wf_id, "default", "standard", "pending")
            return ToolResponse(
                success=True,
                outputs={"workflow_id": wf_id, "status": "pending"},
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Failed to initiate workflow execution: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="workflow-execute",
            name="Workflow Execution Tool",
            version="1.0.0",
            description="Trigger workflow execution runs.",
            category=ToolCategory.WORKFLOW,
            capabilities=[ToolCapability.UTILITY_RUN],
            permissions_required=[ToolPermission.EXECUTE],
        )


class WorkflowValidationTool(Tool):
    """Validates workflow definition layouts and parameter bindings."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "definition" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        defn = request.inputs["definition"]
        # Basic validation: ensure it's a dict and has steps
        if not isinstance(defn, dict) or "steps" not in defn:
            return ToolResponse(
                success=False,
                errors=["Invalid workflow structure. Missing 'steps' list."],
                duration=time.perf_counter() - start_time,
            )
        return ToolResponse(
            success=True,
            outputs={"valid": True, "step_count": len(defn["steps"])},
            duration=time.perf_counter() - start_time,
        )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="workflow-validation",
            name="Workflow Validation Tool",
            version="1.0.0",
            description="Validate workflow definitions schemas or configurations.",
            category=ToolCategory.WORKFLOW,
            capabilities=[ToolCapability.VALIDATE_SCHEMA],
            permissions_required=[ToolPermission.READ],
        )


class RuntimeHealthTool(Tool):
    """Queries underlying database and platform system availability health states."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return True

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        try:
            from app.platform.providers.sqlite_db import sqlite_db_manager

            sqlite_db_manager.verify_health()
            return ToolResponse(
                success=True,
                outputs={
                    "database_healthy": True,
                    "status": "UP",
                },
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Runtime health check failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        try:
            from app.platform.providers.sqlite_db import sqlite_db_manager

            sqlite_db_manager.verify_health()
            return True
        except Exception:
            return False

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="runtime-health",
            name="Runtime Health check Tool",
            version="1.0.0",
            description="Checks persistence and platform runtime engine health status.",
            category=ToolCategory.RUNTIME,
            capabilities=[ToolCapability.UTILITY_RUN],
            permissions_required=[ToolPermission.READ],
        )


class MemoryQueryTool(Tool):
    """Performs read queries over the agent memory database registry."""

    def __init__(self, memory_manager: AgentMemoryManager | None = None) -> None:
        self.memory_manager = memory_manager or AgentMemoryManager()

    async def initialize(self) -> None:
        await self.memory_manager.initialize()

    async def validate(self, request: ToolRequest) -> bool:
        return "query" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        q_str = request.inputs["query"]
        try:
            # Query memory database entries
            entries = await self.memory_manager.db.query_entries(
                context.workflow_id,
                context.execution_id,
                context.agent_id,
                "session",  # default session scope
                MemoryQuery(search_query=q_str),
            )
            return ToolResponse(
                success=True,
                outputs={"results": [e.model_dump() for e in entries]},
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Memory query execution failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        await self.memory_manager.cache.close()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="memory-query",
            name="Memory Query Tool",
            version="1.0.0",
            description="Query and retrieve records from Agent Memory context.",
            category=ToolCategory.KNOWLEDGE_BASE,
            capabilities=[ToolCapability.READ_FILE],
            permissions_required=[ToolPermission.READ],
        )


class MemorySnapshotTool(Tool):
    """Serializes active session memories into a persistent snapshot object."""

    def __init__(self, memory_manager: AgentMemoryManager | None = None) -> None:
        self.memory_manager = memory_manager or AgentMemoryManager()

    async def initialize(self) -> None:
        await self.memory_manager.initialize()

    async def validate(self, request: ToolRequest) -> bool:
        return "snapshot_id" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        try:
            snapshot = await self.memory_manager.create_snapshot(
                context.workflow_id,
                context.execution_id,
                context.agent_id,
                "session",
            )
            return ToolResponse(
                success=True,
                outputs={
                    "snapshot_id": snapshot.snapshot_id,
                    "snapshot_time": snapshot.timestamp,
                },
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Snapshot creation failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        await self.memory_manager.cache.close()

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="memory-snapshot",
            name="Memory Snapshot Tool",
            version="1.0.0",
            description="Freeze and save agent session memory snapshots.",
            category=ToolCategory.KNOWLEDGE_BASE,
            capabilities=[ToolCapability.WRITE_FILE],
            permissions_required=[ToolPermission.WRITE],
        )


class DocumentGeneratorTool(Tool):
    """Compiles markdown documentation pages by interpolating templates."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "template" in request.inputs and "vars" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        tmpl = request.inputs["template"]
        variables = request.inputs["vars"]

        try:
            # Interpolate parameters
            result = tmpl
            for k, v in variables.items():
                result = result.replace(f"{{{{{k}}}}}", str(v))

            # Enforce size limits
            max_size = platform_settings.TOOLS_MAX_DOCUMENT_SIZE
            if len(result) > max_size:
                return ToolResponse(
                    success=False,
                    errors=[
                        f"Document size exceeds limits: {len(result)} > {max_size} bytes."
                    ],
                    duration=time.perf_counter() - start_time,
                )

            return ToolResponse(
                success=True,
                outputs={"document": result, "size_bytes": len(result)},
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Compilation failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="document-generator",
            name="Document Compiler Tool",
            version="1.0.0",
            description="Generates report documentation files by replacing template placeholders.",
            category=ToolCategory.TRANSFORMATION,
            capabilities=[ToolCapability.EXPORT_DATA],
            permissions_required=[ToolPermission.WRITE],
        )


class MarkdownExportTool(Tool):
    """Formats payload parameters into structural markdown files."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "title" in request.inputs and "content" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        title = request.inputs["title"]
        content = request.inputs["content"]

        try:
            markdown = f"# {title}\n\nGenerated on: {time.asctime()}\n\n{content}\n"

            # Enforce export constraints
            max_size = platform_settings.TOOLS_MAX_EXPORT_SIZE
            if len(markdown) > max_size:
                return ToolResponse(
                    success=False,
                    errors=[
                        f"Export size exceeds limits: {len(markdown)} > {max_size} bytes."
                    ],
                    duration=time.perf_counter() - start_time,
                )

            return ToolResponse(
                success=True,
                outputs={"markdown": markdown, "bytes_written": len(markdown)},
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Export formatting failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="markdown-export",
            name="Markdown Export formatter Tool",
            version="1.0.0",
            description="Renders payload results into markdown formatted assets.",
            category=ToolCategory.EXPORT,
            capabilities=[ToolCapability.EXPORT_DATA],
            permissions_required=[ToolPermission.WRITE],
        )


class JsonTransformTool(Tool):
    """Filters, queries, or transforms structural JSON payload attributes."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "data" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        data = request.inputs["data"]
        projection = request.inputs.get("select", [])

        try:
            if not isinstance(data, dict):
                return ToolResponse(
                    success=False,
                    errors=["Input 'data' must be a valid JSON object/dict."],
                    duration=time.perf_counter() - start_time,
                )

            transformed = {}
            if projection:
                for key in projection:
                    if key in data:
                        transformed[key] = data[key]
            else:
                transformed = data

            return ToolResponse(
                success=True,
                outputs={"transformed": transformed},
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"JSON transform failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="json-transform",
            name="JSON Mapping and Transform Tool",
            version="1.0.0",
            description="Filters JSON fields or formats payload data structures.",
            category=ToolCategory.TRANSFORMATION,
            capabilities=[ToolCapability.UTILITY_RUN],
            permissions_required=[ToolPermission.READ],
        )


class SchemaValidationTool(Tool):
    """Validates structural parameters against schema dictionary constraints."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "payload" in request.inputs and "schema" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        payload = request.inputs["payload"]
        schema = request.inputs["schema"]

        try:
            if not isinstance(payload, dict) or not isinstance(schema, dict):
                return ToolResponse(
                    success=False,
                    errors=[
                        "Payload and schema parameters must be dictionary configurations."
                    ],
                    duration=time.perf_counter() - start_time,
                )

            errors = []
            for field, type_name in schema.items():
                if field not in payload:
                    errors.append(f"Missing required field: '{field}'")
                elif type_name == "int" and not isinstance(payload[field], int):
                    errors.append(f"Field '{field}' must be an integer.")
                elif type_name == "str" and not isinstance(payload[field], str):
                    errors.append(f"Field '{field}' must be a string.")

            return ToolResponse(
                success=len(errors) == 0,
                outputs={"valid": len(errors) == 0},
                errors=errors,
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Schema validation failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="schema-validation",
            name="JSON Schema Validation Tool",
            version="1.0.0",
            description="Validate payload parameters against type schemas.",
            category=ToolCategory.VALIDATION,
            capabilities=[ToolCapability.VALIDATE_SCHEMA],
            permissions_required=[ToolPermission.READ],
        )


class TextSearchTool(Tool):
    """Executes keyword or regex searches over a list of texts."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "pattern" in request.inputs and "texts" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        pat = request.inputs["pattern"]
        texts = request.inputs["texts"]

        try:
            if not isinstance(texts, list):
                return ToolResponse(
                    success=False,
                    errors=["Texts parameter must be a list of string elements."],
                    duration=time.perf_counter() - start_time,
                )

            regex = re.compile(pat)
            matches: list[dict[str, Any]] = []
            limit = platform_settings.TOOLS_MAX_SEARCH_RESULTS

            for index, item in enumerate(texts):
                if len(matches) >= limit:
                    break
                if regex.search(str(item)):
                    matches.append({"index": index, "content": str(item)})

            return ToolResponse(
                success=True,
                outputs={"matches": matches, "match_count": len(matches)},
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Text search regex compile or lookup failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="text-search",
            name="Regex and Text Search Tool",
            version="1.0.0",
            description="Scans documents or lists using regex pattern matches.",
            category=ToolCategory.SEARCH,
            capabilities=[ToolCapability.QUERY_DB],
            permissions_required=[ToolPermission.READ],
        )


class VariableResolverTool(Tool):
    """Interpolates system platform variables or context mappings."""

    async def initialize(self) -> None:
        pass

    async def validate(self, request: ToolRequest) -> bool:
        return "expression" in request.inputs

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        start_time = time.perf_counter()
        expr = request.inputs["expression"]

        try:
            # Resolve common execution and platform details
            resolved = expr
            mappings = {
                "workflow_id": context.workflow_id,
                "execution_id": context.execution_id,
                "agent_id": context.agent_id,
            }

            for placeholder, val in mappings.items():
                resolved = resolved.replace(f"${placeholder}", str(val))

            return ToolResponse(
                success=True,
                outputs={"resolved": resolved},
                duration=time.perf_counter() - start_time,
            )
        except Exception as exc:
            return ToolResponse(
                success=False,
                errors=[f"Variable resolution failed: {exc}"],
                duration=time.perf_counter() - start_time,
            )

    async def health(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="variable-resolver",
            name="Variable and Context Resolver Tool",
            version="1.0.0",
            description="Interpolates workflow and platform context parameters.",
            category=ToolCategory.UTILITY,
            capabilities=[ToolCapability.UTILITY_RUN],
            permissions_required=[ToolPermission.READ],
        )
