import getpass
import socket
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Type

import sqlalchemy as sa

from delembic.alembic_compat import AlembicDepsError, check_alembic_deps
from delembic.dag import topological_sort
from delembic.db import ensure_tables, get_applied, record_result
from delembic.migration import DataMigration
from delembic.registry import load_migrations


def run_upgrade(
    engine: sa.Engine,
    versions_dir: Path,
    target: str = "head",
    alembic_ini: Path | None = None,
) -> None:
    migrations = load_migrations(versions_dir)
    if not migrations:
        print("No migrations found.")
        return

    order = topological_sort(migrations)

    username = _safe(getpass.getuser)
    hostname = _safe(socket.gethostname)

    # meta_conn records delembic_version / run_history — always committed independently
    # work_conn runs migration SQL — rolled back on failure without touching meta_conn
    with engine.connect() as meta_conn:
        ensure_tables(meta_conn)
        meta_conn.commit()
        applied = get_applied(meta_conn)

        pending = [rev for rev in order if rev not in applied]

        if target != "head":
            if target not in order:
                raise ValueError(f"Unknown target revision: {target}")
            cutoff = order.index(target)
            pending = [rev for rev in pending if order.index(rev) <= cutoff]

        if not pending:
            print("Already up to date.")
            return

        for revision in pending:
            cls = migrations[revision]
            instance = cls()

            # Validate Alembic deps before attempting to run
            alembic_deps = _external_deps(cls, migrations)
            if alembic_deps:
                if alembic_ini is None:
                    raise SystemExit(
                        f"Migration {revision} depends on Alembic revisions "
                        f"{alembic_deps} but alembic_config is not set in delembic.ini."
                    )
                try:
                    check_alembic_deps(meta_conn, alembic_ini, alembic_deps, revision)
                except AlembicDepsError as e:
                    print(f"  BLOCKED: {e}")
                    raise SystemExit(1)

            print(f"Running {revision}: {cls.description}")
            started_at = datetime.now(timezone.utc)
            t0 = time.monotonic()

            with engine.connect() as work_conn:
                try:
                    instance.upgrade(work_conn)
                    instance.validate(work_conn)
                    ended_at = datetime.now(timezone.utc)
                    duration = time.monotonic() - t0
                    work_conn.commit()
                    record_result(
                        meta_conn, revision, started_at, ended_at, duration,
                        "success", username=username, hostname=hostname,
                    )
                    meta_conn.commit()
                    print(f"  OK ({duration:.2f}s)")

                except Exception as e:
                    ended_at = datetime.now(timezone.utc)
                    duration = time.monotonic() - t0
                    tb = traceback.format_exc()
                    work_conn.rollback()
                    record_result(
                        meta_conn, revision, started_at, ended_at, duration,
                        "failed", exception=tb, username=username, hostname=hostname,
                    )
                    meta_conn.commit()
                    print(f"  FAILED: {e}")
                    raise SystemExit(1)


def _external_deps(
    cls: Type[DataMigration],
    migrations: dict[str, Type[DataMigration]],
) -> list[str]:
    """Return deps that are not Delembic revisions (i.e. Alembic or other external)."""
    return [dep for dep in cls.depends_on if dep not in migrations]


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None
