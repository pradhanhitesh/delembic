# Dependency Tracking

## Declaring Dependencies

Migrations declare dependencies via `depends_on`:

```python
class LoadPerson(DataMigration):
    revision = "D002"
    depends_on = ["D001"]   # D001 must be applied first
```

Delembic builds a directed acyclic graph (DAG) and runs migrations in topological order. File names and filesystem order are irrelevant.

## Dependency Shapes

### Linear chain

```
D001 → D002 → D003
```

```python
class D002(DataMigration):
    revision = "D002"
    depends_on = ["D001"]

class D003(DataMigration):
    revision = "D003"
    depends_on = ["D002"]
```

### Diamond (fan-out / fan-in)

```
       D001
      /    \
   D002    D003
      \    /
       D004
```

```python
class D002(DataMigration):
    revision = "D002"
    depends_on = ["D001"]

class D003(DataMigration):
    revision = "D003"
    depends_on = ["D001"]

class D004(DataMigration):
    revision = "D004"
    depends_on = ["D002", "D003"]
```

D002 and D003 can run in either order (both depend on D001). D004 runs last.

### Independent migrations

```python
class D001(DataMigration):
    revision = "D001"
    depends_on = []

class D002(DataMigration):
    revision = "D002"
    depends_on = []
```

When no dependency exists between two migrations, Delembic runs them in the order it encounters them (stable sort).

## External Dependencies (Alembic Revisions)

`depends_on` can reference Alembic schema migration IDs:

```python
class LoadPerson(DataMigration):
    revision = "D001"
    depends_on = ["3d1e3e6abc12"]   # Alembic revision
```

Delembic identifies external deps as any entry in `depends_on` that is **not** a known Delembic revision. At upgrade time, it verifies those Alembic revisions are applied before running the migration.

See [Alembic Integration](alembic-integration.md) for full details.

## Cycle Detection

Cycles raise `CycleError` at upgrade time:

```python
# This will fail at runtime
class D001(DataMigration):
    revision = "D001"
    depends_on = ["D002"]   # D001 depends on D002...

class D002(DataMigration):
    revision = "D002"
    depends_on = ["D001"]   # ...and D002 depends on D001 → cycle
```

```
delembic.dag.CycleError: Cycle detected involving: D001, D002
```

## Target Upgrades

Run up to a specific revision instead of `head`:

```bash
delembic upgrade D003
```

Delembic runs all pending migrations that are ancestors of D003 (including D003 itself), in dependency order. Migrations after D003 in the DAG are skipped.

## How the DAG Works

Delembic uses **Kahn's algorithm** for topological sort:

1. Build in-degree count for each migration
2. Start with zero-in-degree nodes (no dependencies)
3. Process queue: emit node, decrement in-degrees of dependents, enqueue new zeros
4. If any nodes remain after processing → cycle detected

External dependencies (Alembic revisions, or any ID not in the migrations dict) are silently excluded from the in-degree calculation — they don't block topological sort, only runtime checks verify them.
