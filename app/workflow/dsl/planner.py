"""Workflow Execution Planner to compute stage-based parallel execution plans."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.workflow.dsl.models import WorkflowDefinition


class ExecutionNode(BaseModel):
    """Execution metadata node for a step within the execution plan."""

    model_config = ConfigDict(frozen=True)

    step_id: str = Field(..., description="Unique step identifier.")
    stage_number: int = Field(
        ..., description="The parallel stage number this step belongs to (1-indexed)."
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Step IDs this step directly depends on."
    )
    dependents: list[str] = Field(
        default_factory=list, description="Step IDs that directly depend on this step."
    )
    parallel_group: int = Field(
        default=0, description="0-indexed parallel group position in the stage."
    )
    estimated_inputs: dict[str, Any] = Field(
        default_factory=dict, description="Estimated input schemas."
    )
    estimated_outputs: dict[str, Any] = Field(
        default_factory=dict, description="Estimated output schemas."
    )


class ExecutionStage(BaseModel):
    """A collection of step IDs that can be executed concurrently."""

    model_config = ConfigDict(frozen=True)

    stage_number: int = Field(..., description="Index of this execution stage.")
    steps: list[str] = Field(
        default_factory=list, description="List of step IDs assigned to this stage."
    )


class ExecutionEdge(BaseModel):
    """A directed edge in the dependency DAG."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="Step ID of the dependency source.")
    target: str = Field(..., description="Step ID of the dependent target.")


class ExecutionStatistics(BaseModel):
    """Consolidated planning statistics."""

    model_config = ConfigDict(frozen=True)

    total_steps: int = Field(default=0, description="Total number of steps.")
    root_steps: int = Field(default=0, description="Total number of root steps.")
    leaf_steps: int = Field(default=0, description="Total number of leaf steps.")
    parallel_stages: int = Field(
        default=0, description="Total number of execution stages."
    )
    maximum_parallelism: int = Field(
        default=0, description="Max width of any single stage."
    )
    critical_path_length: int = Field(
        default=0, description="Number of steps in the critical path."
    )
    maximum_graph_depth: int = Field(
        default=0,
        description="Longest graph height (equivalent to critical path length).",
    )
    dependency_count: int = Field(
        default=0, description="Total count of dependency edges."
    )


class ExecutionPlan(BaseModel):
    """The generated execution plan for a workflow run."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str = Field(..., description="Workflow ID reference.")
    stages: list[ExecutionStage] = Field(
        default_factory=list, description="Execution stages in order."
    )
    nodes: dict[str, ExecutionNode] = Field(
        default_factory=dict, description="Map of step ID to execution node metadata."
    )
    edges: list[ExecutionEdge] = Field(
        default_factory=list, description="List of dependency edges in the DAG."
    )
    statistics: ExecutionStatistics = Field(
        ..., description="Consolidated planning metrics."
    )
    critical_path: list[str] = Field(
        default_factory=list, description="Step IDs on the critical execution path."
    )
    mermaid_graph: str = Field(
        ..., description="Mermaid string representing the dependency DAG."
    )


class WorkflowExecutionPlanner:
    """Service class that compiles a WorkflowDefinition into an optimized ExecutionPlan."""

    @staticmethod
    def plan(workflow: WorkflowDefinition) -> ExecutionPlan:
        """Generates a deterministic execution plan from a workflow definition.

        Args:
            workflow: The validated workflow definition.

        Returns:
            The generated ExecutionPlan.
        """
        # Short-circuit on empty steps list
        if not workflow.steps:
            return ExecutionPlan(
                workflow_id=workflow.id,
                stages=[],
                nodes={},
                edges=[],
                statistics=ExecutionStatistics(),
                critical_path=[],
                mermaid_graph="graph TD\n  Empty[Empty Workflow]",
            )

        step_ids = {s.id for s in workflow.steps}
        steps_map = {s.id: s for s in workflow.steps}

        # Build parents/children adjacency lists
        parents: dict[str, list[str]] = {s.id: [] for s in workflow.steps}
        children: dict[str, list[str]] = {s.id: [] for s in workflow.steps}

        for step in workflow.steps:
            for dep in step.depends_on:
                if dep in step_ids:
                    parents[step.id].append(dep)
                    children[dep].append(step.id)

        # 1. Topological Sorting (Kahn's algorithm)
        in_degree = {s_id: len(p_list) for s_id, p_list in parents.items()}
        queue = [node for node, deg in in_degree.items() if deg == 0]
        topo_order: list[str] = []

        while queue:
            node = queue.pop(0)
            topo_order.append(node)
            for child in children[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        # 2. Stage Generation (Layering stages based on dependency resolution levels)
        stage_map: dict[str, int] = {}
        for node in topo_order:
            node_deps = parents[node]
            if not node_deps:
                stage_map[node] = 1
            else:
                stage_map[node] = max(stage_map[dep] for dep in node_deps) + 1

        # Group steps by stage number
        stages_dict: dict[int, list[str]] = {}
        for node, stage_num in stage_map.items():
            if stage_num not in stages_dict:
                stages_dict[stage_num] = []
            stages_dict[stage_num].append(node)

        # Sort stages list
        execution_stages: list[ExecutionStage] = []
        for s_num in sorted(stages_dict.keys()):
            # Sort step IDs within stage for determinism
            sorted_steps = sorted(stages_dict[s_num])
            execution_stages.append(
                ExecutionStage(stage_number=s_num, steps=sorted_steps)
            )

        # 3. Create ExecutionNode metadata
        execution_nodes: dict[str, ExecutionNode] = {}
        for stage in execution_stages:
            for p_idx, step_id in enumerate(stage.steps):
                step = steps_map[step_id]
                exec_node = ExecutionNode(
                    step_id=step_id,
                    stage_number=stage.stage_number,
                    dependencies=parents[step_id],
                    dependents=children[step_id],
                    parallel_group=p_idx,
                    estimated_inputs=step.input,
                    estimated_outputs=step.output,
                )
                execution_nodes[step_id] = exec_node

        # 4. Generate edges list
        edges: list[ExecutionEdge] = []
        for step_id, child_ids in children.items():
            for child_id in child_ids:
                edges.append(ExecutionEdge(source=step_id, target=child_id))
        # Sort edges for deterministic output
        edges.sort(key=lambda e: (e.source, e.target))

        # 5. Critical Path Calculation (Longest Path in DAG)
        longest_path_to: dict[str, list[str]] = {}
        for node in topo_order:
            node_deps = parents[node]
            if not node_deps:
                longest_path_to[node] = [node]
            else:
                # Select the parent path with max nodes length
                best_parent = max(node_deps, key=lambda d: len(longest_path_to[d]))
                longest_path_to[node] = longest_path_to[best_parent] + [node]

        critical_path: list[str] = []
        if longest_path_to:
            critical_path = max(longest_path_to.values(), key=len)

        # 6. Calculate statistics
        total_steps = len(workflow.steps)
        root_steps = sum(1 for s_id, p in parents.items() if not p)
        leaf_steps = sum(1 for s_id, c in children.items() if not c)
        parallel_stages = len(execution_stages)
        max_parallelism = (
            max(len(stage.steps) for stage in execution_stages)
            if execution_stages
            else 0
        )
        crit_len = len(critical_path)
        dep_count = len(edges)

        stats = ExecutionStatistics(
            total_steps=total_steps,
            root_steps=root_steps,
            leaf_steps=leaf_steps,
            parallel_stages=parallel_stages,
            maximum_parallelism=max_parallelism,
            critical_path_length=crit_len,
            maximum_graph_depth=crit_len,
            dependency_count=dep_count,
        )

        # 7. Generate Mermaid Graph
        mermaid_lines = ["graph TD"]
        for node_id in sorted(step_ids):
            # Define node label with its step name
            name_label = steps_map[node_id].name
            mermaid_lines.append(f'  {node_id}["{name_label}"]')

        for edge in edges:
            mermaid_lines.append(f"  {edge.source} --> {edge.target}")

        mermaid_graph = "\n".join(mermaid_lines)

        return ExecutionPlan(
            workflow_id=workflow.id,
            stages=execution_stages,
            nodes=execution_nodes,
            edges=edges,
            statistics=stats,
            critical_path=critical_path,
            mermaid_graph=mermaid_graph,
        )
