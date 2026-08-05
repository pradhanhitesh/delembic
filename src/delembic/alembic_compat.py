from pathlib import Path

import sqlalchemy as sa


class AlembicDepsError(Exception):
    pass


def get_alembic_applied_revisions(
    conn: sa.Connection, alembic_ini: Path, ini_section: str = "alembic"
) -> set[str]:
    """
    Walk Alembic script history from current heads back to base.
    Returns all revision IDs that have been applied (i.e. are ancestors of current heads).
    Requires alembic to be installed.
    """
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
    except ImportError:
        raise AlembicDepsError(
            "alembic package not installed. Run: pip install alembic"
        )

    alembic_cfg = AlembicConfig(str(alembic_ini), ini_section=ini_section)
    script = ScriptDirectory.from_config(alembic_cfg)
    ctx = MigrationContext.configure(conn)
    current_heads = ctx.get_current_heads()

    applied: set[str] = set()
    for head in current_heads:
        for rev in script.iterate_revisions(head, "base"):
            applied.add(rev.revision)

    return applied


def get_current_heads(conn: sa.Connection) -> list[str]:
    """Return the current Alembic head revision IDs from alembic_version table."""
    try:
        from alembic.runtime.migration import MigrationContext
    except ImportError:
        raise AlembicDepsError(
            "alembic package not installed. Run: pip install alembic"
        )

    ctx = MigrationContext.configure(conn)
    return list(ctx.get_current_heads())


def check_alembic_deps(
    conn: sa.Connection,
    alembic_ini: Path,
    required: list[str],
    migration_revision: str,
    ini_section: str = "alembic",
) -> None:
    """Raise AlembicDepsError if any required Alembic revision has not been applied."""
    applied = get_alembic_applied_revisions(conn, alembic_ini, ini_section)
    missing = [rev for rev in required if rev not in applied]
    if missing:
        raise AlembicDepsError(
            f"Migration {migration_revision} requires Alembic revision(s) "
            f"{', '.join(missing)} to be applied first. "
            f"Run 'alembic upgrade head' (or to the required revision) before retrying."
        )
