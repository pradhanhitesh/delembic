import re
import string
from pathlib import Path

import click
import sqlalchemy as sa

from delembic.config import Config, find_config
from delembic.db import ensure_tables, get_applied, history_table, version_table
from delembic.executor import run_upgrade
from delembic.registry import load_migrations

_INI_TEMPLATE = """\
[delembic]
script_location = delembic
sqlalchemy.url = postgresql+psycopg://user:pass@localhost/mydb
alembic_config = alembic.ini
"""

_ENV_TEMPLATE = """\
from sqlalchemy import create_engine

# Configure your database URL here or load from environment variables
DATABASE_URL = "postgresql+psycopg://user:pass@localhost/mydb"


def get_engine():
    return create_engine(DATABASE_URL)
"""

_MIGRATION_TEMPLATE = """\
from delembic import DataMigration


class $class_name(DataMigration):

    revision = "$revision"

    depends_on = $depends_on

    description = "$description"

    def upgrade(self, conn):
        pass

    def validate(self, conn):
        pass
"""


@click.group()
def cli() -> None:
    """Delembic — data migration framework."""


@cli.command()
@click.argument("directory", default="delembic")
def init(directory: str) -> None:
    """Initialize a new delembic project in the current directory.

    DIRECTORY is the folder name for migration scripts (default: delembic).
    """
    cwd = Path.cwd()
    ini_path = cwd / "delembic.ini"
    script_dir = cwd / directory
    versions_dir = script_dir / "versions"

    if ini_path.exists():
        raise click.ClickException("delembic.ini already exists.")

    ini_content = _INI_TEMPLATE.replace("script_location = delembic", f"script_location = {directory}")

    versions_dir.mkdir(parents=True, exist_ok=True)
    ini_path.write_text(ini_content)
    (script_dir / "env.py").write_text(_ENV_TEMPLATE)
    (versions_dir / ".gitkeep").touch()

    click.echo(f"Created {ini_path}")
    click.echo(f"Created {script_dir / 'env.py'}")
    click.echo(f"Created {versions_dir}/")
    click.echo("\nEdit delembic.ini and set sqlalchemy.url before running migrations.")


@cli.command()
@click.option("-m", "--message", required=True, help="Short description of this migration.")
def revision(message: str) -> None:
    """Generate a new migration file."""
    from delembic.alembic_compat import AlembicDepsError, get_current_heads

    cfg = find_config()
    cfg.versions_dir.mkdir(parents=True, exist_ok=True)

    alembic_heads: list[str] = []
    if cfg.alembic_config:
        try:
            engine = cfg.engine()
            with engine.connect() as conn:
                alembic_heads = get_current_heads(conn)
        except AlembicDepsError as e:
            click.echo(f"Warning: could not read Alembic heads: {e}", err=True)
        except Exception as e:
            click.echo(f"Warning: could not connect to DB for Alembic heads: {e}", err=True)

    next_id = _next_revision_id(cfg.versions_dir)
    slug = re.sub(r"[^a-z0-9]+", "_", message.lower()).strip("_")
    filename = f"{next_id}_{slug}.py"
    class_name = "".join(word.title() for word in slug.split("_"))
    content = string.Template(_MIGRATION_TEMPLATE).substitute(
        class_name=class_name,
        revision=next_id,
        description=message,
        depends_on=repr(alembic_heads),
    )
    path = cfg.versions_dir / filename
    path.write_text(content)
    if alembic_heads:
        click.echo(f"  Alembic heads captured: {alembic_heads}")
    click.echo(f"Created {path}")


@cli.command()
@click.argument("target", default="head")
def upgrade(target: str) -> None:
    """Run unapplied migrations up to TARGET (default: head)."""
    cfg = find_config()
    engine = cfg.engine()
    run_upgrade(engine, cfg.versions_dir, target, alembic_ini=cfg.alembic_config)


@cli.command()
def current() -> None:
    """Show the most recently applied revision."""
    cfg = find_config()
    engine = cfg.engine()
    with engine.connect() as conn:
        try:
            ensure_tables(conn)
            conn.commit()
            row = conn.execute(
                sa.select(version_table.c.revision, version_table.c.applied_at)
                .where(version_table.c.status == "success")
                .order_by(version_table.c.applied_at.desc())
                .limit(1)
            ).fetchone()
        except Exception as e:
            raise click.ClickException(str(e))

    if row:
        click.echo(f"{row[0]}  (applied {row[1]})")
    else:
        click.echo("No migrations applied yet.")


@cli.command()
def history() -> None:
    """List all migrations and their status."""
    cfg = find_config()
    migrations = load_migrations(cfg.versions_dir)

    engine = cfg.engine()
    with engine.connect() as conn:
        try:
            ensure_tables(conn)
            conn.commit()
            applied = get_applied(conn)
            failed_rows = conn.execute(
                sa.select(version_table.c.revision)
                .where(version_table.c.status == "failed")
            )
            failed = {row[0] for row in failed_rows}
        except Exception as e:
            raise click.ClickException(str(e))

    if not migrations:
        click.echo("No migrations found.")
        return

    from delembic.dag import topological_sort
    order = topological_sort(migrations)

    for rev in order:
        cls = migrations[rev]
        if rev in applied:
            status = "applied "
        elif rev in failed:
            status = "failed  "
        else:
            status = "pending "
        click.echo(f"{status}  {rev}  {cls.description}")


def _next_revision_id(versions_dir: Path) -> str:
    existing = list(versions_dir.glob("D*.py"))
    max_n = 0
    for p in existing:
        m = re.match(r"D(\d+)", p.stem)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"D{max_n + 1:03d}"
