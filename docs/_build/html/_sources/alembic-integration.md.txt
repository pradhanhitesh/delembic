# Alembic Integration

Delembic integrates with Alembic to enforce that schema migrations are applied before data migrations that depend on them.

## Setup

Point `alembic_config` at your `alembic.ini`:

```ini
[delembic]
script_location = delembic
sqlalchemy.url = postgresql+psycopg://user:pass@localhost/mydb
alembic_config = alembic.ini
```

`alembic_config` is resolved relative to `delembic.ini`.

Install alembic if not already present:

```bash
pip install alembic
```

## Auto-Capture on Revision Generation

When `alembic_config` is set, `delembic revision` automatically captures the current Alembic head revision(s) into `depends_on`:

```bash
# Alembic is at head: 3d1e3e6abc12
delembic revision -m "load person"
#   Alembic heads captured: ['3d1e3e6abc12']
#   Created delembic/versions/D001_load_person.py
```

Generated file:

```python
class LoadPerson(DataMigration):
    revision = "D001"
    depends_on = ['3d1e3e6abc12']   # ← captured automatically
    description = "load person"
```

If the database is unreachable at revision-generation time, Delembic prints a warning and generates the file with `depends_on = []` — you can fill it in manually.

## Runtime Verification

At `delembic upgrade head`, before running any migration, Delembic checks that all Alembic revisions in `depends_on` are applied:

```
Running D001: load person
  BLOCKED: Migration D001 requires Alembic revision(s) ['3d1e3e6abc12'] to be applied first.
  Run 'alembic upgrade head' before retrying.
```

The blocked migration is not attempted. Delembic exits with code 1.

## Typical Workflow

```bash
# 1. Run schema migrations first
alembic upgrade head

# 2. Run data migrations
delembic upgrade head
```

In CI/CD pipelines:

```yaml
- run: alembic upgrade head
- run: delembic upgrade head
```

## Multiple Alembic Heads

If your Alembic project uses multiple heads (branches), Delembic captures all current heads:

```bash
# Alembic has two active branches
delembic revision -m "post-merge data load"
#   Alembic heads captured: ['3d1e3e6abc12', 'a1b2c3d4e5f6']
```

```python
depends_on = ['3d1e3e6abc12', 'a1b2c3d4e5f6']
```

Both must be applied before the migration runs.

## Without Alembic

Alembic integration is entirely optional. If `alembic_config` is not set in `delembic.ini`:
- `delembic revision` generates files with `depends_on = []`
- `delembic upgrade` skips Alembic checks
- No alembic package needed

## How It Works Internally

Delembic uses two Alembic APIs:

**`get_current_heads(conn)`** — reads `alembic_version` table via `MigrationContext`:

```python
from alembic.runtime.migration import MigrationContext
ctx = MigrationContext.configure(conn)
heads = list(ctx.get_current_heads())
```

**`get_alembic_applied_revisions(conn, alembic_ini)`** — walks script history from current heads back to base via `ScriptDirectory.iterate_revisions()`. Returns the set of all applied revision IDs (not just heads — ancestors included).

This means a migration that depends on `3d1e3e6abc12` will pass verification even if Alembic has since advanced to `a1b2c3d4e5f6`, as long as `3d1e3e6abc12` is an ancestor of the current head.
