# Agent Tool Calling Framework

This document outlines the architecture, contracts, security, configuration, and execution lifecycle of the provider-agnostic Agent Tool Calling Framework in SafeSeed-Ops.

---

## 1. Architecture Overview

The Tool Calling Framework enables concrete agents to discover and invoke localized tools (e.g. database querying, filesystem access, HTTP clients) consistently. The Workflow Engine interacts with tools purely through abstract interfaces, ensuring decoupled security validation and lifecycle management.

```mermaid
graph TD
    WorkflowEngine[Workflow Engine] --> AgentManager[Agent Manager]
    AgentManager --> ToolManager[Tool Manager]
    ToolManager --> ToolRegistry[Tool Registry]
    ToolRegistry --> ToolInterface["Tool Interface (Abstract)"]
    ToolInterface --> ConcreteToolA[Concrete Tool Alpha]
    ToolInterface --> ConcreteToolB[Concrete Tool Beta]
```

---

## 2. Tool Lifecycle

Concrete tools transition through the following states during validation, execution, and resource cleanup:

```mermaid
stateDiagram-v2
    [*] --> Registered
    Registered --> Initialized: initialize()
    Initialized --> Validated: validate(request)
    Validated --> Executed: execute(request, context)
    Executed --> CleanedUp: cleanup()
    CleanedUp --> [*]
    Validated --> CleanedUp: Validation Failure / Exception
```

---

## 3. Permission Model

To guarantee secure execution sandboxes, the framework enforces a role-based permission model. Concrete tools declare their required permissions in their metadata. The `ToolManager` inspects these requirements before initialization and blocks execution on missing permissions.

### Supported Permissions:
* **Read / Write:** Local storage read/write capabilities.
* **Execute:** Running script binaries or commands.
* **Admin:** Privileged administrative access.
* **Network:** External API requests and socket actions.
* **Filesystem:** Direct disk read/write access.
* **Database:** SQL/NoSQL transaction capabilities.
* **Environment:** Accessing process environment variables.

---

## 4. Registration Flow

The `ToolRegistry` manages the thread-safe lifecycle and capability grouping of active tools:

```mermaid
sequenceDiagram
    autonumber
    Developer ->> ToolRegistry: register(concrete_tool)
    alt ID already exists
        ToolRegistry -->> Developer: ToolRegistryError (Duplicate ID)
    else Unique ID
        ToolRegistry ->> ToolRegistry: Store tool in thread-safe dict
        ToolRegistry -->> Developer: Success
    end
```

---

## 5. Execution Flow

The `ToolManager` coordinates resolving, permission checking, timeout enforcement, concurrency limits, and retry loops:

```mermaid
sequenceDiagram
    autonumber
    Agent ->> ToolManager: execute_tool(tool_id, inputs, context, permissions)
    ToolManager ->> ToolRegistry: lookup(tool_id)
    ToolRegistry -->> ToolManager: tool instance
    loop Permission Verification
        ToolManager ->> ToolManager: Check required vs granted permissions
    end
    alt Permission Denied
        ToolManager -->> Agent: ToolResponse (Failed - Permission Denied)
    else Permission Granted
        ToolManager ->> ToolManager: Acquire Concurrency Semaphore
        ToolManager ->> Tool: initialize()
        ToolManager ->> Tool: validate(request)
        alt Inputs Invalid
            ToolManager ->> Tool: cleanup()
            ToolManager -->> Agent: ToolResponse (Failed - Input Invalid)
        else Inputs Valid
            loop Retry Block (up to max_retries)
                ToolManager ->> Tool: execute(request, context) wrapped in wait_for(timeout)
                Tool -->> ToolManager: ToolResponse
            end
            ToolManager ->> Tool: cleanup()
            ToolManager -->> Agent: ToolResponse
        end
    end
```

---

## 6. Configuration Settings

All runtime parameters are fetched dynamically from `PlatformSettings` (no hardcoded settings):
* `platform_settings.TOOLS_MAX_EXECUTION_TIMEOUT_SECONDS` — Ceiling limit for execution durations before throwing a timeout.
* `platform_settings.TOOLS_MAX_CONCURRENT_EXECUTIONS` — Maximum parallel tool runs allowed concurrently (semaphore size).
* `platform_settings.TOOLS_MAX_RETRIES` — Maximum retry attempts on transient step failures.

---

## 7. Development Integration Example

To create a custom tool:
```python
from app.agents.tools import Tool, ToolMetadata, ToolCategory, ToolCapability, ToolPermission, ToolRequest, ToolResponse, ToolContext

class QueryDatabaseTool(Tool):
    async def initialize(self) -> None:
        pass
        
    async def validate(self, request: ToolRequest) -> bool:
        return "query" in request.inputs
        
    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        # DB Query execution
        return ToolResponse(success=True, outputs={"results": [...]}, duration=0.05)
        
    async def health(self) -> bool:
        return True
        
    async def cleanup(self) -> None:
        pass
        
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id="query-db",
            name="Database Query Tool",
            version="1.0.0",
            category=ToolCategory.DATABASE,
            capabilities=[ToolCapability.QUERY_DB],
            permissions_required=[ToolPermission.DATABASE, ToolPermission.READ]
        )
```
