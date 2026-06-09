# Internals

Architecture overview for contributors and advanced users.

## Package Structure

```
src/delembic/
├── __init__.py          # public API: DataMigration, __version__
├── migration.py         # DataMigration ABC
├── registry.py          # dynamic class loader
├── dag.py               # topological sort (Kahn's algorithm)
├── db.py                # SQLAlchemy table definitions, record_result
├── executor.py          # run_upgrade, dual-connection architecture
├── config.py            # Config, find_config
├── alembic_compat.py    # Alembic integration (lazy imports)
└── cli.py               # Click commands
```

## Execution Model

### Dual-Connection Architecture

`run_upgrade` opens two separate database connections per migration:

```
meta_conn   ─── delembic_version, delembic_run_history  ─── always committed
work_conn   ─── your migration SQL                       ─── rolled back on failure
```

This solves a real production problem: if a single connection is used, `conn.rollback()` on migration failure would also roll back the failure record in `delembic_version`. With dual connections, the audit trail always survives.

```python
with engine.connect() as meta_conn:
    # reads applied set, writes audit records
    with engine.connect() as work_conn:
        try:
            instance.upgrade(work_conn)
            instance.validate(work_conn)
            work_conn.commit()
            record_result(meta_conn, ..., "success")
            meta_conn.commit()
        except Exception:
            work_conn.rollback()
            record_result(meta_conn, ..., "failed")
            meta_conn.commit()
            raise SystemExit(1)
```

### Retry Semantics

`record_result` does DELETE + INSERT on `delembic_version` (not upsert):

```python
conn.execute(sa.delete(version_table).where(version_table.c.revision == revision))
conn.execute(sa.insert(version_table).values(...))
conn.execute(sa.insert(history_table).values(...))   # always append
```

This means:
- `delembic_version` always reflects the *latest* outcome
- `delembic_run_history` is append-only — full audit of every attempt

## DAG Module

`dag.py` implements Kahn's algorithm:

1. Build adjacency list and in-degree map from `depends_on`
2. External deps (IDs not in the migrations dict) are excluded from the graph — they don't affect sort order, only runtime checks
3. Process zero-in-degree queue
4. Any remaining nodes after full processing → `CycleError`

```python
def topological_sort(migrations: dict[str, Type[DataMigration]]) -> list[str]:
    ...
    # external deps silently skipped — treated as satisfied by the sort
    in_degree = {rev: 0 for rev in migrations}
    for rev, cls in migrations.items():
        for dep in cls.depends_on:
            if dep in migrations:   # only internal deps affect the graph
                in_degree[rev] += 1
                graph[dep].append(rev)
    ...
```

## Registry Module

`registry.py` uses `importlib` to load migration classes dynamically:

1. Glob `versions/*.py`, skip files starting with `_`
2. `importlib.util.spec_from_file_location` + `module_from_spec` + `exec_module`
3. Inspect all module attributes; collect subclasses of `DataMigration` with a `revision` attribute
4. Return `{revision: class}` dict

## Config Resolution

`find_config()` walks up from `Path.cwd()` looking for `delembic.ini`. This means you can run `delembic` commands from any subdirectory.

`alembic_config` is resolved as an absolute path relative to `delembic.ini`'s directory — not relative to cwd.

## Alembic Compatibility Module

`alembic_compat.py` uses lazy imports:

```python
def get_current_heads(conn):
    try:
        from alembic.runtime.migration import MigrationContext
    except ImportError:
        raise ImportError("alembic is not installed. Run: pip install alembic")
    ...
```

This keeps alembic as an optional dependency — the package works without it unless Alembic integration is actually used.

`get_alembic_applied_revisions` walks the full ancestry of current heads using `ScriptDirectory.iterate_revisions(head, "base")`. This returns all applied revisions, not just the tip — so `depends_on = ["old_revision"]` passes even after Alembic has advanced further.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests use:
- `pytest` with `CliRunner` for CLI tests
- `sqlite:///:memory:` for most DB tests
- File-based SQLite (`sqlite:///tmp/test.db`) where cross-connection state persistence is needed (failure recording tests)
- `unittest.mock.patch` for Alembic integration tests (no real Alembic needed)
- `tmp_path` fixture + `runner.isolated_filesystem()` for CLI tests that read/write files
