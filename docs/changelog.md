# Changelog

## 0.6.0

- **`delembic serve`** — localhost web UI for visualizing migration history
  - Overview tab: side-by-side Schema (Alembic) and Data (Delembic) panels
  - Schema tab: full Alembic revision chain with applied/pending status
  - Data tab: Delembic migrations with status, duration, user@host, and collapsible error tracebacks
  - Stats bar: applied/failed/pending counts; DB URL shown with password masked
  - Refresh button: fetches live data without a full page reload
  - Also runnable as `python -m delembic.server [--port PORT] [--no-browser]`

## 0.5.0

- **Pipeline orchestration** — new `delembic pipeline` command group
  - `pipeline init` — create a starter `pipeline.yaml`
  - `pipeline run [--file]` — execute steps in sequence, stop on failure
  - `pipeline generate [--output] [--print]` — auto-generate an interleaved pipeline by reading the Alembic revision chain and each Delembic migration's `depends_on`
  - `pipeline run --auto` — generate and execute in one step, no YAML file needed
- Alembic pipeline steps use the programmatic API (no subprocess)
- `pyyaml` added as a runtime dependency

## 0.4.0

- **UUID-based revision IDs** — replaced sequential `D001`, `D002`, … counters with 12-character hex strings (e.g. `3a9f1c2e8b4d`), matching Alembic's convention; no scanning of existing files required
- **Alembic-style filenames** — `YYYY_MM_DD_HHmmss_<revision>_<slug>.py` format, configurable via `filename_template` in `delembic.ini`
- Migration templates moved from inline Python strings to `.mako` files; `mako` added as a runtime dependency

## 0.3.0

- **`sqlalchemy.url` now optional** — Delembic falls back to calling `get_engine()` from `<script_location>/env.py` when the URL is not set in `delembic.ini`; `env.py` is the recommended single source of truth when using Alembic alongside Delembic
- **`filename_template`** — configurable filename format in `delembic.ini` with `%(year)s`, `%(month)s`, `%(day)s`, `%(hour)s`, `%(minute)s`, `%(second)s`, `%(revision)s`, `%(slug)s` variables
- Switched to `configparser.RawConfigParser` to prevent `%(...)s` interpolation conflicts with `filename_template`

## 0.2.0

- **Read the Docs documentation** — Sphinx + Furo + MyST-parser; hosted at readthedocs.io
- **PyPI Trusted Publishing** — OIDC-based publish workflow; no stored API token required
- CI/CD release workflow skips (does not fail) on commits without a `bump:` keyword

## 0.1.0 — Initial Release

- `DataMigration` ABC with `upgrade()` and `validate()` hooks
- DAG-based execution with topological sort (Kahn's algorithm)
- `delembic init`, `revision`, `upgrade`, `current`, `history` CLI commands
- `delembic_version` and `delembic_run_history` metadata tables
- Dual-connection executor: audit records survive transaction rollbacks
- Alembic integration: auto-capture heads on `revision`, verify deps on `upgrade`
- `bump2version` + GitHub Actions release workflow
