# Delembic

Data migration framework for Python — Alembic for ETL and data operations.

Alembic versions schema changes. Delembic versions **data** changes: vocabulary loads, ETL runs, reference data inserts, corrections. Together they describe the complete database state.

## Installation

```bash
pip install delembic
```

## Quick Start

```bash
# 1. Initialize in your project
delembic init

# 2. Edit delembic.ini — set your database URL
#    sqlalchemy.url = postgresql+psycopg://user:pass@host/dbname

# 3. Create a migration
delembic revision -m "load vocabulary"

# 4. Fill in the generated file, then run
delembic upgrade head
```

## Configuration

`delembic init` creates:

```
your-project/
├── delembic.ini          # config — commit this
└── delembic/
    ├── env.py            # optional connection helpers
    └── versions/         # migration files live here
```

**`delembic.ini`:**

```ini
[delembic]
script_location = delembic
sqlalchemy.url = postgresql+psycopg://user:pass@localhost/mydb
alembic_config = alembic.ini
```

You can name the script folder anything:

```bash
delembic init data-migrations
```

## Writing Migrations

```python
from delembic import DataMigration

class LoadVocabulary(DataMigration):

    revision = "D001"
    depends_on = []
    description = "Load OMOP vocabulary tables"

    def upgrade(self, conn):
        conn.execute(...)

    def validate(self, conn):
        count = conn.execute("SELECT COUNT(*) FROM concept").scalar()
        assert count > 0, "vocabulary load produced no rows"
```

`conn` is a SQLAlchemy `Connection`. `validate` is optional — migration is marked failed if it raises.

## Dependency Tracking

Migrations declare explicit dependencies. Delembic builds a DAG and runs them in topological order.

```python
class LoadPerson(DataMigration):
    revision = "D002"
    depends_on = ["D001"]   # waits for D001
```

## Alembic Integration

Point `alembic_config` at your `alembic.ini`:

```ini
[delembic]
alembic_config = alembic.ini
```

When you create a migration, Delembic automatically captures the current Alembic head:

```bash
delembic revision -m "load person"
# → depends_on = ['3d1e3e6abc12']   (current alembic head)
```

At upgrade time, Delembic verifies the required Alembic revision has been applied before running:

```
BLOCKED: Migration D002 requires Alembic revision(s) 3d1e3e6abc12 to be applied first.
Run 'alembic upgrade head' before retrying.
```

## CLI Reference

| Command | Description |
|---|---|
| `delembic init [DIR]` | Initialize project. DIR defaults to `delembic` |
| `delembic revision -m "msg"` | Generate new migration file |
| `delembic upgrade head` | Run all pending migrations |
| `delembic upgrade D003` | Run migrations up to D003 |
| `delembic current` | Show last applied revision |
| `delembic history` | List all migrations with status |

## Metadata Tables

Delembic creates two tables:

```sql
delembic_version       -- current status per revision
delembic_run_history   -- full audit log (start/end time, duration, exception, user, host)
```

Failed migration work is rolled back. The failure record is always committed — audit trail survives transaction failures.

## Development

```bash
pip install -e ".[dev]"
pytest
```
