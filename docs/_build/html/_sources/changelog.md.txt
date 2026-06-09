# Changelog

## 0.1.0 — Initial Release

- `DataMigration` ABC with `upgrade()` and `validate()` hooks
- DAG-based execution with topological sort (Kahn's algorithm)
- `delembic init`, `revision`, `upgrade`, `current`, `history` CLI commands
- `delembic_version` and `delembic_run_history` metadata tables
- Dual-connection executor: audit records survive transaction rollbacks
- Alembic integration: auto-capture heads on `revision`, verify deps on `upgrade`
- `bump2version` + GitHub Actions release workflow
