import configparser
import re
import uuid
from datetime import datetime
from pathlib import Path

import click
import sqlalchemy as sa
from mako.template import Template

from delembic.config import Config, find_config
from delembic.db import ensure_tables, get_applied, history_table, version_table
from delembic.executor import run_upgrade
from delembic.registry import load_migrations

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _render(name: str, **kwargs: object) -> str:
    return Template(filename=str(_TEMPLATES_DIR / name)).render(**kwargs)


@click.group()
@click.option(
    "-c", "--config", "config_path",
    type=click.Path(path_type=Path), default=None,
    help="Path to a delembic ini file (default: search upward for delembic.ini).",
)
@click.option(
    "-n", "--name", "section", default="delembic", show_default=True,
    help="Named config section to use (mirrors alembic's -n).",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None, section: str) -> None:
    """Delembic — data migration framework."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["section"] = section


def _find_config(ctx: click.Context) -> Config:
    try:
        return find_config(ctx.obj["config_path"], ctx.obj["section"])
    except FileNotFoundError as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("directory", default="delembic")
@click.pass_context
def init(ctx: click.Context, directory: str) -> None:
    """Initialize a new delembic project, or add a named section to an existing one.

    DIRECTORY is the folder name for migration scripts (default: delembic).
    Use -n/--name to add another section (e.g. bronze/silver/gold) to an
    existing delembic.ini instead of creating a new file.
    """
    section = ctx.obj["section"]
    cwd = Path.cwd()
    ini_path = ctx.obj["config_path"] or (cwd / "delembic.ini")
    script_dir = cwd / directory
    versions_dir = script_dir / "versions"

    if ini_path.exists():
        cp = configparser.RawConfigParser()
        cp.read(ini_path)
        if cp.has_section(section):
            raise click.ClickException(f"[{section}] already exists in {ini_path}.")
        cp.add_section(section)
        cp.set(section, "script_location", directory)
        cp.set(section, "alembic_config", "alembic.ini")
        cp.set(
            section,
            "filename_template",
            "%(year)s_%(month)s_%(day)s_%(hour)s%(minute)s%(second)s_%(revision)s_%(slug)s",
        )
        with ini_path.open("w") as f:
            cp.write(f)
    else:
        if section != "delembic":
            raise click.ClickException(
                f"{ini_path} does not exist yet; run 'delembic init' without -n first."
            )
        ini_content = _render("delembic.ini.mako", script_location=directory)
        ini_path.write_text(ini_content)

    versions_dir.mkdir(parents=True, exist_ok=True)
    (script_dir / "env.py").write_text(_render("env.py.mako"))
    (versions_dir / ".gitkeep").touch()

    click.echo(f"Updated {ini_path}  [{section}]")
    click.echo(f"Created {script_dir / 'env.py'}")
    click.echo(f"Created {versions_dir}/")
    click.echo("\n[IMPORTANT] Edit delembic/env.py and set DATABASE_URL before running migrations.")
    click.echo("\n[IMPORTANT] Edit delembic.ini and set alembic_config before running migrations.")


@cli.command()
@click.option("-m", "--message", required=True, help="Short description of this migration.")
@click.pass_context
def revision(ctx: click.Context, message: str) -> None:
    """Generate a new migration file."""
    from delembic.alembic_compat import AlembicDepsError, get_current_heads

    cfg = _find_config(ctx)
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

    next_id = uuid.uuid4().hex[:12]
    slug = re.sub(r"[^a-z0-9]+", "_", message.lower()).strip("_")
    now = datetime.now()
    filename = (cfg.filename_template % {
        "revision": next_id,
        "slug": slug,
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
        "hour": now.strftime("%H"),
        "minute": now.strftime("%M"),
        "second": now.strftime("%S"),
    }) + ".py"
    class_name = "".join(word.title() for word in slug.split("_"))
    content = _render(
        "migration.mako",
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
@click.pass_context
def upgrade(ctx: click.Context, target: str) -> None:
    """Run unapplied migrations up to TARGET (default: head)."""
    cfg = _find_config(ctx)
    engine = cfg.engine()
    run_upgrade(
        engine, cfg.versions_dir, target,
        alembic_ini=cfg.alembic_config, project_root=cfg.ini_path.parent,
    )


@cli.command()
@click.pass_context
def current(ctx: click.Context) -> None:
    """Show the most recently applied revision."""
    cfg = _find_config(ctx)
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
@click.option("--port", default=8800, show_default=True, help="Port to listen on.")
@click.option("--no-browser", is_flag=True, default=False, help="Don't open browser automatically.")
@click.pass_context
def serve(ctx: click.Context, port: int, no_browser: bool) -> None:
    """Start a localhost UI to visualize migration history."""
    from delembic.server import serve as _serve

    cfg = _find_config(ctx)
    _serve(cfg, port=port, open_browser=not no_browser)


@cli.group()
def pipeline() -> None:
    """Manage and run orchestration pipelines."""


@pipeline.command("init")
@click.option("--file", "filename", default="pipeline.yaml", show_default=True, help="Output filename.")
def pipeline_init(filename: str) -> None:
    """Create a starter pipeline.yaml in the current directory."""
    dest = Path.cwd() / filename
    if dest.exists():
        raise click.ClickException(f"{filename} already exists.")
    template = _TEMPLATES_DIR / "pipeline.yaml"
    dest.write_text(template.read_text())
    click.echo(f"Created {dest}")
    click.echo("Edit the file to add/reorder steps, then run: delembic pipeline run")


@pipeline.command("generate")
@click.option("--output", default="pipeline.yaml", show_default=True, help="File to write.")
@click.option("--print", "print_only", is_flag=True, default=False, help="Print to stdout instead of writing a file.")
@click.pass_context
def pipeline_generate(ctx: click.Context, output: str, print_only: bool) -> None:
    """Auto-generate pipeline.yaml from alembic + delembic dependency graphs."""
    from delembic.pipeline_gen import generate_pipeline, pipeline_to_yaml

    cfg = _find_config(ctx)
    try:
        pl = generate_pipeline(cfg)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    yaml_text = pipeline_to_yaml(pl)

    if print_only:
        click.echo(yaml_text)
        return

    dest = Path.cwd() / output
    if dest.exists():
        click.confirm(f"{output} already exists. Overwrite?", abort=True)
    dest.write_text(yaml_text)
    click.echo(f"Generated {dest}  ({len(pl.steps)} steps)")
    click.echo("Review and edit if needed, then run: delembic pipeline run")


@pipeline.command("run")
@click.option("--file", "filename", default="pipeline.yaml", show_default=True, help="Pipeline YAML to execute.")
@click.option("--auto", is_flag=True, default=False, help="Auto-generate pipeline from dependency graph instead of reading a file.")
@click.pass_context
def pipeline_run(ctx: click.Context, filename: str, auto: bool) -> None:
    """Execute the pipeline (from FILE or auto-generated with --auto)."""
    from delembic.pipeline import run_pipeline

    cfg = _find_config(ctx)

    if auto:
        from delembic.pipeline_gen import generate_pipeline
        try:
            pl = generate_pipeline(cfg)
        except RuntimeError as e:
            raise click.ClickException(str(e))
        click.echo(f"Auto-generated pipeline  ({len(pl.steps)} steps)")
    else:
        from delembic.pipeline import Pipeline
        path = Path.cwd() / filename
        if not path.exists():
            raise click.ClickException(
                f"{filename} not found. Use --auto or run 'delembic pipeline generate' first."
            )
        try:
            pl = Pipeline.from_file(path)
        except (ValueError, Exception) as e:
            raise click.ClickException(str(e))
        click.echo(f"Running pipeline: {filename}  ({len(pl.steps)} steps)")

    try:
        run_pipeline(pl, cfg)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.pass_context
def history(ctx: click.Context) -> None:
    """List all migrations and their status."""
    cfg = _find_config(ctx)
    migrations = load_migrations(cfg.versions_dir, cfg.ini_path.parent)

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


