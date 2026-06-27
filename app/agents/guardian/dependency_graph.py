"""Dependency graph mapping SQL tables and resolving execution orders."""

from app.agents.guardian.exceptions import (
    DependencyCycleError,
    UnresolvedDependencyError,
)


class DependencyGraph:
    """Graph structure managing SQL table dependencies and topological sorting."""

    def __init__(self) -> None:
        """Initialize an empty DependencyGraph."""
        self.nodes: set[str] = set()
        self.adj: dict[str, set[str]] = {}  # u -> set(v) where u is a dependency of v
        self.in_degree: dict[str, int] = {}  # node -> number of incoming edges
        self.dependencies: dict[str, set[str]] = {}  # v -> set(u) where v depends on u

    def add_node(self, node: str) -> None:
        """Register a node in the graph if it doesn't already exist.

        Args:
            node: The table name.
        """
        name = node.lower().strip()
        if name not in self.nodes:
            self.nodes.add(name)
            self.adj[name] = set()
            self.in_degree[name] = 0
            self.dependencies[name] = set()

    def add_edge(self, u: str, v: str) -> None:
        """Add a directed edge from u to v indicating that table u is a dependency of table v.

        Args:
            u: Dependency table name (parent).
            v: Dependent table name (child).
        """
        u_name = u.lower().strip()
        v_name = v.lower().strip()

        self.add_node(u_name)
        self.add_node(v_name)

        # Self-dependency checks are ignored or handled gracefully
        if u_name == v_name:
            return

        if v_name not in self.adj[u_name]:
            self.adj[u_name].add(v_name)
            self.in_degree[v_name] += 1
            self.dependencies[v_name].add(u_name)

    def validate_dependencies(self, declared_tables: set[str]) -> None:
        """Verify all referenced tables exist within the declared set of tables.

        Args:
            declared_tables: Set of table names defined in the SQL schema.

        Raises:
            UnresolvedDependencyError: If a foreign key references a missing table.
        """
        declared_lower = {t.lower().strip() for t in declared_tables}
        for node in self.nodes:
            for dep in self.dependencies.get(node, set()):
                if dep not in declared_lower:
                    raise UnresolvedDependencyError(
                        f"Table '{node}' references undeclared table '{dep}' via foreign key."
                    )

    def get_topological_sort_and_layers(
        self,
    ) -> tuple[list[str], list[list[str]], dict[str, int]]:
        """Run Kahn's algorithm to resolve topological sort, execution groups, and levels.

        Returns:
            Tuple[List[str], List[List[str]], Dict[str, int]]:
                (ordered_tables, execution_groups, dependency_levels)

        Raises:
            DependencyCycleError: If a cycle is detected in the graph.
        """
        in_deg = dict(self.in_degree)

        groups: list[list[str]] = []
        ordered_tables: list[str] = []
        dependency_levels: dict[str, int] = {}

        # Layer 0 starts with nodes having no incoming dependencies (in-degree == 0)
        current_layer = [n for n in self.nodes if in_deg[n] == 0]
        current_layer.sort()  # Sort alphabetically for determinism

        level = 0
        while current_layer:
            groups.append(current_layer)
            next_layer: list[str] = []

            for u in current_layer:
                ordered_tables.append(u)
                dependency_levels[u] = level

                # Decrement in-degrees for dependent neighbors
                for v in sorted(
                    self.adj[u]
                ):  # Sort neighbors alphabetically for determinism
                    in_deg[v] -= 1
                    if in_deg[v] == 0:
                        next_layer.append(v)

            next_layer.sort()  # Sort next layer alphabetically for determinism
            current_layer = next_layer
            level += 1

        # Cycle check
        if len(ordered_tables) < len(self.nodes):
            cycle_candidates = [n for n in self.nodes if in_deg[n] > 0]
            cycle_candidates.sort()
            raise DependencyCycleError(
                f"Dependency cycle detected among tables: {', '.join(cycle_candidates)}"
            )

        return ordered_tables, groups, dependency_levels
