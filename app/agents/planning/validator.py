"""PlanValidator enforcing graph structures, dependencies, cycles, and capabilities checks."""

from app.agents.planning.models import ExecutionPlan, PlanningContext


class PlanValidationError(Exception):
    """Exception raised on validation failures."""

    pass


class PlanValidator:
    """Enforces execution plan rules, cycles, capabilities, and connectivity validation."""

    @staticmethod
    def validate_plan(plan: ExecutionPlan, context: PlanningContext) -> list[str]:
        """Validate an execution plan against structural, capability, and relational rules.

        Returns:
            List[str]: A list of diagnostic error strings. If empty, the plan is valid.
        """
        errors: list[str] = []

        # 1. Validate Invalid References in Edges
        for edge in plan.edges:
            if edge.from_id not in plan.nodes:
                errors.append(
                    f"Edge from_id '{edge.from_id}' points to a non-existent task node."
                )
            if edge.to_id not in plan.nodes:
                errors.append(
                    f"Edge to_id '{edge.to_id}' points to a non-existent task node."
                )

        if errors:
            # relational integrity failed; stop early to prevent key errors in graph traversals
            return errors

        # 2. Cycle Detection (Circular Dependencies) using DFS/Topological sorting
        visited: dict[str, int] = {
            node_id: 0 for node_id in plan.nodes
        }  # 0=unvisited, 1=visiting, 2=visited

        def has_cycle(node_id: str) -> bool:
            visited[node_id] = 1
            # Check outbound edges (downstream dependencies)
            for edge in plan.edges:
                if edge.from_id == node_id:
                    nxt = edge.to_id
                    if visited[nxt] == 1:
                        return True
                    if visited[nxt] == 0 and has_cycle(nxt):
                        return True
            visited[node_id] = 2
            return False

        for node_id in plan.nodes:
            if visited[node_id] == 0 and has_cycle(node_id):
                errors.append(
                    "Circular dependency detected in execution plan task graph."
                )
                break

        # 3. Missing Capabilities Verification
        system_caps = set(context.system_capabilities)
        for node_id, node in plan.nodes.items():
            for cap in node.required_capabilities:
                if cap not in system_caps:
                    errors.append(
                        f"Task '{node_id}' requires capability '{cap}' which is missing in context."
                    )

        # 4. Missing Tools Verification
        available_tools = set(context.available_tools)
        for node_id, node in plan.nodes.items():
            for tool in node.required_tools:
                if tool not in available_tools:
                    errors.append(
                        f"Task '{node_id}' requires tool '{tool}' which is not available in registry."
                    )

        # 5. Connectedness / Reachability Checks
        # The graph is disconnected if there is more than 1 task, and any task has no incoming and no outgoing edges.
        if len(plan.nodes) > 1:
            for node_id in plan.nodes:
                has_incoming = any(edge.to_id == node_id for edge in plan.edges)
                has_outgoing = any(edge.from_id == node_id for edge in plan.edges)
                if not has_incoming and not has_outgoing:
                    errors.append(
                        f"Task '{node_id}' is completely disconnected from the task graph."
                    )

        return errors
