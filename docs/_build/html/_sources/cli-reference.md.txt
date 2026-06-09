# CLI Reference

## Global

```
delembic [OPTIONS] COMMAND [ARGS]...
```

Delembic walks up from the current directory to find `delembic.ini`. You can run commands from any subdirectory.

---

## `delembic init`

Initialize a new project.

```bash
delembic init [DIRECTORY]
```

**Arguments**

`DIRECTORY`
: Folder name for migration scripts. **Default:** `delembic`

**Examples**

```bash
delembic init                   # creates delembic/
delembic init data-migrations   # creates data-migrations/
```

**Creates**

```
./delembic.ini
./delembic/
./delembic/env.py
./delembic/versions/
./delembic/versions/.gitkeep
```

**Errors**
- Exits with error if `delembic.ini` already exists.

---

## `delembic revision`

Generate a new migration file.

```bash
delembic revision -m MESSAGE
```

**Options**

`-m, --message TEXT`
: *(Required)* Short description. Used as filename slug and `description` attribute.

**Examples**

```bash
delembic revision -m "load vocabulary"
# → delembic/versions/D001_load_vocabulary.py

delembic revision -m "load person demographics"
# → delembic/versions/D002_load_person_demographics.py
```

**Behavior**
- Revision IDs auto-increment: `D001`, `D002`, `D003`, …
- If `alembic_config` is set in `delembic.ini`, connects to DB and captures current Alembic heads into `depends_on`
- If DB unreachable: prints warning, generates file with `depends_on = []`

---

## `delembic upgrade`

Run unapplied migrations.

```bash
delembic upgrade [TARGET]
```

**Arguments**

`TARGET`
: Revision ID to upgrade to, or `head` for all pending. **Default:** `head`

**Examples**

```bash
delembic upgrade head    # run all pending
delembic upgrade D003    # run up to and including D003
```

**Behavior**
- Resolves migration order via topological sort
- Skips already-applied migrations
- Checks Alembic deps before each migration (if `alembic_config` set)
- On failure: rolls back migration work, commits failure record, exits with code 1

**Output**

```
Running D001: load vocabulary
  OK (1.24s)
Running D002: load person demographics
  OK (0.87s)
```

---

## `delembic current`

Show the most recently applied revision.

```bash
delembic current
```

**Output**

```
D002  (applied 2024-01-15 10:30:00+00:00)
```

Or if nothing applied:

```
No migrations applied yet.
```

---

## `delembic history`

List all migrations with their status.

```bash
delembic history
```

**Output**

```
applied   D001  load vocabulary
applied   D002  load person demographics
pending   D003  load drug exposure
failed    D004  load observation
```

**Status values**

| Status | Meaning |
|---|---|
| `applied` | Last run succeeded |
| `failed` | Last run failed |
| `pending` | Never run |

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Migration failed, Alembic dep blocked, or config error |
