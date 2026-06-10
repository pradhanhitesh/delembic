# Pipeline Orchestration

When Alembic and Delembic are used together, schema migrations and data migrations must run in the correct interleaved order. The pipeline feature handles this automatically.

## The Problem

Suppose your project has this history:

```
alembic:  schema v1 → schema v2 → schema v3
delembic: load vocab (needs v1) → load demographics (needs v2)
```

Running `alembic upgrade head` then `delembic upgrade head` applies all schema first, then all data — but `load vocab` could have run earlier (after v1), and `load demographics` only needed v2 not v3. For short pipelines this is fine. For long pipelines with hours of data loading, interleaving reduces total time and makes failures easier to diagnose.

## Auto-Generated Pipeline

The simplest approach — let Delembic figure out the order:

```bash
delembic pipeline run --auto
```

Delembic reads:
1. The Alembic revision chain (`alembic.ini` script location) — ordered base → head
2. Each Delembic migration's `depends_on` field — which Alembic revision was HEAD when the migration was created

It emits an interleaved sequence that upgrades Alembic to each checkpoint before running the data migrations that depend on it.

### Example

Given:

| Migration | Type | `depends_on` |
|---|---|---|
| `3a9f1c2e8b4d` (load vocab) | delembic | `["abc123def456"]` (alembic rev) |
| `a1b2c3d4e5f6` (load demographics) | delembic | `["def789abc012"]` (alembic rev) |

Alembic chain: `abc123def456 → def789abc012 → 7c8d9e0f1a2b`

Auto-generated pipeline:

```
[1] alembic upgrade abc123def456
[2] delembic upgrade 3a9f1c2e8b4d   ← load vocab
[3] alembic upgrade def789abc012
[4] delembic upgrade a1b2c3d4e5f6   ← load demographics
[5] alembic upgrade head
[6] delembic upgrade head            ← catches any remainder
```

## Manual Pipeline

For full control, create a `pipeline.yaml` file:

```bash
delembic pipeline init      # creates starter pipeline.yaml
```

Edit `pipeline.yaml`:

```yaml
steps:
  - name: "Apply schema v1"
    type: alembic
    target: abc123def456

  - name: "Load vocabulary"
    type: delembic
    target: 3a9f1c2e8b4d

  - name: "Apply remaining schema"
    type: alembic
    target: head

  - name: "Load remaining data"
    type: delembic
    target: head
```

Run it:

```bash
delembic pipeline run
```

### `pipeline.yaml` reference

Each step requires:

| Field | Type | Description |
|---|---|---|
| `name` | string | Human-readable label shown in output |
| `type` | `alembic` \| `delembic` | Which tool to invoke |
| `target` | string | Revision ID or `head` |

## Generate and Review

If you want to inspect the auto-generated plan before running it:

```bash
delembic pipeline generate           # writes pipeline.yaml
delembic pipeline generate --print   # prints to stdout
```

Review the file, edit if needed, then run:

```bash
delembic pipeline run
```

This gives you the convenience of auto-generation with the safety of a committed, reviewable artifact.

## Requirements

- `alembic_config` must be set in `delembic.ini` to use `pipeline generate` or `--auto`
- Alembic must have a single head — resolve multiple heads with `alembic merge heads` first
- `alembic` must be installed (`pip install alembic`)

## Behavior

- Steps run in sequence; any failure stops the pipeline immediately
- Alembic steps use the programmatic API (no subprocess)
- Delembic steps use the same retry-safe, audit-logged executor as `delembic upgrade`
- Idempotent — already-applied migrations are skipped at both the Alembic and Delembic layers

```{note}
`depends_on` in a Delembic migration records the Alembic HEAD at the time `delembic revision` was run.
This is what the pipeline generator uses as the checkpoint. If you created a migration while on an
older Alembic revision, the checkpoint will reflect that older revision — which is the correct behavior.
```
