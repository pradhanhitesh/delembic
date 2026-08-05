# AGENT.md — Delembic

Data migration framework for versioning ETL and data operations alongside Alembic schema migrations. Python ≥3.11, SQLAlchemy ≥2.0.

## What it does

- Manages data migrations (ETL, seed data, backfills) with versioning and audit trails
- Integrates with Alembic: migrations can declare Alembic schema revisions as prerequisites
- Provides pipeline orchestration to interleave Alembic schema steps with Delembic data steps

## Package layout

```
src/delembic/
├── migration.py      # DataMigration ABC — the base class users subclass
├── registry.py       # loads migration classes from versions/*.py via importlib
├── dag.py            # topological_sort (Kahn's) + ancestors_of (DFS)
├── db.py             # SQLAlchemy table defs: delembic_version, delembic_run_history
├── executor.py       # run_upgrade — core execution loop with dual-connection model
├── config.py         # Config (reads delembic.ini) + find_config (walks up from cwd)
├── alembic_compat.py # lazy Alembic imports — keeps alembic optional
├── cli.py            # Click commands: init, revision, upgrade, current, history, serve, pipeline
├── pipeline.py       # Pipeline/Step dataclasses + run_pipeline
├── pipeline_gen.py   # auto-generates Pipeline from alembic chain + delembic deps
├── server.py         # localhost UI for migration history
└── templates/        # Mako templates for generated files
```

## Core abstractions

### DataMigration (migration.py)

```python
class MyMigration(DataMigration):
    revision = "abc123def456"          # 12-char hex, set by `delembic revision`
    description = "load vocab table"
    depends_on = ["alembic_rev_id"]    # Alembic OR Delembic revision IDs

    def upgrade(self, conn: Connection) -> None: ...
    def validate(self, conn: Connection) -> None: ...  # optional, runs after upgrade
```

`depends_on` is mixed — any ID not in the Delembic migrations dict is treated as an external (Alembic) dep.

### Config (config.py)

Reads `delembic.ini`. `Config(ini_path, section="delembic")` reads a named section (default `"delembic"`); raises `FileNotFoundError` if a non-default section is missing. Key fields (all section-scoped):
- `script_location` — directory containing `versions/` and `env.py`
- `sqlalchemy.url` — direct DB URL; if absent, loads `env.py` and calls `get_engine()`
- `alembic_config` — path to `alembic.ini` (required for Alembic integration)
- `filename_template` — strftime-style template for generated migration filenames

`find_config(ini_path=None, section="delembic")` — with `ini_path` given, loads that file directly; otherwise walks up from `cwd` to find `delembic.ini`. This backs the CLI's `-c/--config` and `-n/--name` options (mirrors Alembic's own `-n`), letting one ini host multiple named sections (e.g. `[bronze]`/`[silver]`/`[gold]`), each with its own `versions/` dir and DB. `cli.py`'s `_find_config(ctx)` wraps `FileNotFoundError` into `click.ClickException` — always go through it (or `find_config` + that same wrapping) rather than calling `find_config()` bare in new commands.

### Executor (executor.py)

`run_upgrade(engine, versions_dir, target="head", alembic_ini=None)`

**Dual-connection model** — critical invariant:
- `meta_conn` — reads applied set, writes audit records; always committed independently
- `work_conn` — runs user migration SQL; rolled back on failure without affecting `meta_conn`

This ensures the audit trail (`delembic_run_history`) survives migration failures.

**Target upgrade**: when `target != "head"`, uses `ancestors_of(migrations, target)` — only runs migrations in the transitive dependency set of the target. Unrelated peer migrations at the same DAG depth are skipped.

**Failure behavior**: `record_result` does DELETE + INSERT on `delembic_version` (not upsert) so status always reflects the latest attempt. `delembic_run_history` is append-only.

### DAG (dag.py)

Two functions:

`topological_sort(migrations)` → `list[str]`
- Kahn's algorithm
- External deps (IDs absent from migrations dict) silently excluded from sort
- Raises `CycleError` if a cycle exists

`ancestors_of(migrations, target)` → `set[str]`
- Iterative DFS returning target + all transitive Delembic dependencies
- Does NOT follow external (Alembic) deps — only traverses internal migration IDs

### Pipeline (pipeline.py + pipeline_gen.py)

`Pipeline` holds a list of `Step(name, type, target)` where `type` is `"alembic"` or `"delembic"`.

`generate_pipeline(cfg)` auto-builds a pipeline:
1. Gets Alembic revision chain (base → head)
2. Groups Delembic migrations by their Alembic checkpoint (`depends_on` external ID)
3. For each checkpoint: emit one alembic step, then one delembic step **per migration** in the group (sorted by topological order)
4. Appends `alembic → head` and `delembic → head` as final steps

Each migration in a group gets its own step. The executor's `ancestors_of` logic handles idempotency at the Delembic layer.

## DB schema

`delembic_version` — one row per revision, reflects latest status (`success` | `failed`)
`delembic_run_history` — append-only audit log of every attempt

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Test patterns:
- `patch("delembic.executor.load_migrations", return_value=migrations)` — inject migrations without files
- `sqlite:///:memory:` for most tests; file-based SQLite for failure recording tests (cross-connection state)
- `patch("delembic.executor.check_alembic_deps", ...)` — mock Alembic dep checks

## Adding a new CLI command

1. Add a `@cli.command()` or `@<group>.command()` in `cli.py`, decorated with `@click.pass_context`
2. Call `cfg = _find_config(ctx)` first (not `find_config()` directly — it threads the group-level `-n/-c` options and wraps missing-section errors), then `cfg.engine()` if DB access needed
3. Use `load_migrations(cfg.versions_dir)` to load migrations
4. Raise `click.ClickException(str(e))` for user-facing errors

## Key invariants — don't break these

1. `meta_conn` and `work_conn` must stay separate in `run_upgrade`. Merging them breaks failure auditing.
2. `record_result` must DELETE then INSERT (not upsert) to allow retries.
3. External deps in `depends_on` must NOT be followed by `ancestors_of` — only internal Delembic IDs.
4. `alembic_compat.py` must use lazy imports — Alembic is optional.
5. `registry.py` skips files starting with `_` — keep that convention for private/helper files in `versions/`.

## Optional dependency: Alembic

Alembic is not in `dependencies` — it's optional. All Alembic imports go through `alembic_compat.py` with `try/except ImportError`. Never add top-level Alembic imports elsewhere.

## Versioning

Uses `.bumpversion.cfg`. Release pipeline in `.github/workflows/release.yml`.
