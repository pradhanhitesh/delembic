from typing import Type

from delembic.migration import DataMigration


class CycleError(Exception):
    pass


def topological_sort(migrations: dict[str, Type[DataMigration]]) -> list[str]:
    """Return revision IDs in dependency-safe execution order (Kahn's algorithm)."""
    in_degree: dict[str, int] = {rev: 0 for rev in migrations}
    dependents: dict[str, list[str]] = {rev: [] for rev in migrations}

    for rev, cls in migrations.items():
        for dep in cls.depends_on:
            if dep not in migrations:
                # External dep (e.g. Alembic revision) — skip in sort, validate at runtime
                continue
            in_degree[rev] += 1
            dependents[dep].append(rev)

    queue = sorted(rev for rev, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        node = queue.pop(0)
        order.append(node)
        for dependent in sorted(dependents.get(node, [])):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(migrations):
        raise CycleError("Cycle detected in migration dependency graph")

    return order


def ancestors_of(migrations: dict[str, Type[DataMigration]], target: str) -> set[str]:
    """Return target plus all its transitive delembic dependencies (not unrelated peers)."""
    visited: set[str] = set()
    stack = [target]
    while stack:
        rev = stack.pop()
        if rev in visited:
            continue
        visited.add(rev)
        cls = migrations.get(rev)
        if cls is None:
            continue
        for dep in cls.depends_on:
            if dep in migrations:
                stack.append(dep)
    return visited
