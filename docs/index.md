# Delembic

**Data migration framework for Python — Alembic for ETL and data operations.**

Alembic versions schema changes. Delembic versions **data** changes: vocabulary loads, ETL runs, reference data inserts, corrections. Together they describe the complete state of your database.

```{note}
Delembic is designed to work alongside Alembic, not replace it. Schema migrations stay in Alembic; data migrations move to Delembic.
```

## Why Delembic?

- **Declarative migrations** — write a class, declare dependencies, run
- **DAG-based execution** — topological sort ensures correct order regardless of file names
- **Alembic integration** — verifies schema migrations are applied before data migrations run
- **Pipeline orchestration** — interleave schema and data migrations in the correct order, auto-generated from dependency graph
- **Migration history UI** — `delembic serve` opens a localhost dashboard showing applied/pending/failed status for both Alembic and Delembic
- **Audit trail** — every run recorded; failure records survive transaction rollbacks
- **Retry-safe** — failed migrations can be re-run; state table reflects latest outcome

## Quick Install

```bash
pip install delembic
```

## Contents

```{toctree}
:maxdepth: 2
:caption: User Guide

getting-started
configuration
writing-migrations
dependency-tracking
alembic-integration
pipeline
cli-reference
```

```{toctree}
:maxdepth: 1
:caption: Reference

internals
changelog
```
