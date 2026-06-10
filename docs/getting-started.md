# Getting Started

## Installation

```bash
pip install delembic
```

For Alembic integration (optional):

```bash
pip install delembic alembic
```

## Requirements

- Python 3.11+
- SQLAlchemy 2.0+
- A running database (PostgreSQL, SQLite, MySQL — anything SQLAlchemy supports)

## Project Setup

### 1. Initialize

Run `delembic init` in the root of your project:

```bash
delembic init
```

This creates:

```
your-project/
├── delembic.ini          ← config file (commit this)
└── delembic/
    ├── env.py            ← set your database URL here
    └── versions/         ← migration files live here
        └── .gitkeep
```

You can name the migrations folder anything:

```bash
delembic init data-migrations
```

### 2. Configure Database URL

Edit `delembic/env.py` and set your database URL:

```python
# delembic/env.py
from sqlalchemy import create_engine

DATABASE_URL = "postgresql+psycopg://user:pass@localhost/mydb"

def get_engine():
    return create_engine(DATABASE_URL)
```

Delembic calls `get_engine()` from `env.py` automatically. `sqlalchemy.url` in `delembic.ini` is optional — it takes precedence if set, but `env.py` is the recommended approach when using Alembic alongside Delembic (one source of truth).

### 3. Create Your First Migration

```bash
delembic revision -m "load vocabulary"
```

A new file appears in `delembic/versions/`:

```python
# delembic/versions/D001_load_vocabulary.py

from delembic import DataMigration

class LoadVocabulary(DataMigration):
    revision = "D001"
    depends_on = []
    description = "load vocabulary"

    def upgrade(self, conn):
        # conn is a SQLAlchemy Connection — use it to run SQL or pass to your loaders
        # Example:
        #   from sqlalchemy import text
        #   conn.execute(text("INSERT INTO my_table SELECT * FROM staging.my_table"))
        pass

    def validate(self, conn):
        pass
```

### 4. Write the Migration

Fill in `upgrade()` (and optionally `validate()`):

```python
def upgrade(self, conn):
    conn.execute(
        text("INSERT INTO concept SELECT * FROM concept_staging")
    )

def validate(self, conn):
    count = conn.execute(text("SELECT COUNT(*) FROM concept")).scalar()
    assert count > 0, "no rows loaded"
```

### 5. Run

```bash
delembic upgrade head
```

Output:

```
Running D001: load vocabulary
  OK (1.24s)
```

### 6. Check Status

```bash
delembic current
# D001  (applied 2024-01-15 10:30:00+00:00)

delembic history
# applied   D001  load vocabulary
```

## What Happens Under the Hood

1. Delembic loads all migration classes from `delembic/versions/`
2. Builds a DAG from `depends_on` declarations
3. Topologically sorts → determines run order
4. For each pending migration:
   - Opens a **work connection** for your SQL
   - Opens a **metadata connection** for audit records
   - Runs `upgrade()` then `validate()` on work connection
   - On success: commits work, writes `success` to metadata
   - On failure: rolls back work, writes `failed` to metadata (audit survives)
