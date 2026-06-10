# Configuration

## `delembic.ini`

Delembic reads configuration from `delembic.ini`. It walks up from the current directory, so you can run `delembic` commands from any subdirectory of your project.

### Full example

```ini
[delembic]
script_location = delembic
# sqlalchemy.url = postgresql+psycopg://user:pass@localhost/mydb
# If not set, Delembic calls get_engine() from delembic/env.py
alembic_config = alembic.ini
```

### Options

`script_location`
: Path to the folder containing `versions/`. Relative to the location of `delembic.ini`. **Default:** `delembic`

`sqlalchemy.url`
: SQLAlchemy database URL. **Optional.** If set, takes precedence over `env.py`. If omitted, Delembic loads `<script_location>/env.py` and calls `get_engine()`. Examples:
  ```
  postgresql+psycopg://user:pass@localhost/mydb
  postgresql+psycopg2://user:pass@localhost/mydb
  sqlite:///data.db
  ```

`alembic_config`
: Path to your `alembic.ini`. Relative to `delembic.ini`. Optional — only needed if you use Alembic integration. When set, `delembic revision` will auto-capture current Alembic heads into `depends_on`.

## `env.py` — Database Connection

`delembic init` generates `<script_location>/env.py`. This is the recommended way to configure the database URL, especially when using Alembic alongside Delembic (one source of truth):

```python
# delembic/env.py
import os
from sqlalchemy import create_engine

DATABASE_URL = os.environ["DATABASE_URL"]

def get_engine():
    return create_engine(DATABASE_URL)
```

**Resolution order:**
1. `sqlalchemy.url` set in `delembic.ini` → used directly
2. Not set → `<script_location>/env.py` loaded, `get_engine()` called
3. Neither → error

`env.py` must define a `get_engine()` function that returns a `sqlalchemy.Engine`.

## Custom Folder Name

```bash
delembic init data-migrations
```

`delembic.ini` is updated automatically:

```ini
[delembic]
script_location = data-migrations
```

## Metadata Tables

Delembic automatically creates two tables on first run:

### `delembic_version`

Current status per revision. One row per revision, replaced on retry.

| Column | Type | Description |
|---|---|---|
| `revision` | TEXT | Revision ID (e.g. `3a9f1c2e8b4d`) |
| `status` | TEXT | `success` or `failed` |
| `applied_at` | DATETIME | When this run started |
| `duration_seconds` | FLOAT | How long the migration took |
| `username` | TEXT | OS user who ran the migration |
| `hostname` | TEXT | Hostname where migration ran |

### `delembic_run_history`

Full append-only audit log. Every run appended, never deleted.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `revision` | TEXT | Revision ID |
| `status` | TEXT | `success` or `failed` |
| `started_at` | DATETIME | Run start time |
| `ended_at` | DATETIME | Run end time |
| `duration_seconds` | FLOAT | Duration |
| `exception` | TEXT | Full traceback (failures only) |
| `username` | TEXT | OS user |
| `hostname` | TEXT | Hostname |

```{note}
Failed migration work is rolled back. The failure record is always committed on a separate connection — the audit trail survives transaction failures.
```
