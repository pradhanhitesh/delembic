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
# → delembic/versions/2026_06_10_151205_3a9f1c2e8b4d_load_vocabulary.py

delembic revision -m "load person demographics"
# → delembic/versions/2026_06_10_151230_a1b2c3d4e5f6_load_person_demographics.py
```

**Behavior**
- Revision IDs are 12-character hex strings (`uuid4().hex[:12]`), matching Alembic's convention
- Filename format: `YYYY_MM_DD_HHmmss_<revision>_<slug>.py` (configurable via `filename_template` in `delembic.ini`)
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
delembic upgrade head           # run all pending
delembic upgrade 3a9f1c2e8b4d  # run up to and including that revision
```

**Behavior**
- Resolves migration order via topological sort
- Skips already-applied migrations
- Checks Alembic deps before each migration (if `alembic_config` set)
- On failure: rolls back migration work, commits failure record, exits with code 1

**Output**

```
Running 3a9f1c2e8b4d: load vocabulary
  OK (1.24s)
Running a1b2c3d4e5f6: load person demographics
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
a1b2c3d4e5f6  (applied 2026-06-10 15:12:05+00:00)
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
applied   3a9f1c2e8b4d  load vocabulary
applied   a1b2c3d4e5f6  load person demographics
pending   7c8d9e0f1a2b  load drug exposure
failed    4b5c6d7e8f9a  load observation
```

**Status values**

| Status | Meaning |
|---|---|
| `applied` | Last run succeeded |
| `failed` | Last run failed |
| `pending` | Never run |

---

---

## `delembic pipeline`

Orchestrate Alembic schema migrations and Delembic data migrations in a defined sequence.

```bash
delembic pipeline COMMAND [OPTIONS]
```

---

### `delembic pipeline init`

Create a starter `pipeline.yaml` in the current directory.

```bash
delembic pipeline init [--file FILENAME]
```

**Options**

`--file TEXT`
: Output filename. **Default:** `pipeline.yaml`

**Example**

```bash
delembic pipeline init
```

Creates:

```yaml
steps:
  - name: Apply schema migrations
    type: alembic
    target: head

  - name: Apply data migrations
    type: delembic
    target: head
```

Edit the file to add checkpoints, reorder steps, or interleave schema and data migrations.

---

### `delembic pipeline generate`

Auto-generate `pipeline.yaml` by reading the Alembic revision chain and each Delembic migration's `depends_on` field. Produces an interleaved pipeline that applies schema to each checkpoint before running the data migrations that depend on it.

```bash
delembic pipeline generate [--output FILENAME] [--print]
```

**Options**

`--output TEXT`
: File to write. **Default:** `pipeline.yaml`

`--print`
: Print generated YAML to stdout instead of writing a file.

**Example**

```bash
delembic pipeline generate --print
```

```yaml
steps:
- name: Schema → abc123def456
  type: alembic
  target: abc123def456
- name: 'Data: load vocabulary'
  type: delembic
  target: 3a9f1c2e8b4d
- name: Schema → head
  type: alembic
  target: head
- name: Data migrations → head
  type: delembic
  target: head
```

**How it works**

Each Delembic migration's `depends_on` contains the Alembic revision that was HEAD when the file was generated. `pipeline generate` reads these to determine checkpoints — the specific Alembic revisions that must be applied before each data migration can run. It then emits an `alembic upgrade <checkpoint>` step followed by the corresponding `delembic upgrade <revision>` step for each checkpoint, finishing with `alembic upgrade head` and `delembic upgrade head` to cover any remainder.

**Requirements**
- `alembic_config` must be set in `delembic.ini`
- Alembic must have a single head (merge branches before generating if you have multiple)

---

### `delembic pipeline run`

Execute a pipeline.

```bash
delembic pipeline run [--file FILENAME] [--auto]
```

**Options**

`--file TEXT`
: Pipeline YAML to execute. **Default:** `pipeline.yaml`

`--auto`
: Auto-generate the pipeline from the dependency graph at runtime — no YAML file needed. Equivalent to `pipeline generate` followed immediately by execution.

**Examples**

```bash
delembic pipeline run                        # run pipeline.yaml
delembic pipeline run --file deploy/prod.yaml
delembic pipeline run --auto                 # generate + run in one step
```

**Behavior**
- Steps run in sequence; failure stops the pipeline immediately
- Alembic steps use the programmatic API (not subprocess)
- Delembic steps respect the existing retry-safe, audit-logged executor
- Each step prints elapsed time on completion

**Output**

```
Auto-generated pipeline  (4 steps)

[1/4] Schema → abc123def456  (alembic → abc123def456)
    done in 0.8s
[2/4] Data: load vocabulary  (delembic → 3a9f1c2e8b4d)
Running 3a9f1c2e8b4d: load vocabulary
  OK (1.24s)
    done in 1.3s
[3/4] Schema → head  (alembic → head)
    done in 0.1s
[4/4] Data migrations → head  (delembic → head)
Already up to date.
    done in 0.0s

Pipeline complete — 4 step(s) ran.
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Migration failed, Alembic dep blocked, or config error |
