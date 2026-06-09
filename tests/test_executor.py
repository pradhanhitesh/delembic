from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from delembic.db import ensure_tables, get_applied
from delembic.executor import run_upgrade
from delembic.migration import DataMigration


def _engine():
    return sa.create_engine("sqlite:///:memory:")


def _make(revision: str, depends_on: list[str] = [], fail: bool = False):
    def upgrade(self, conn):
        if fail:
            raise RuntimeError(f"upgrade failed for {revision}")

    return type(revision, (DataMigration,), {
        "revision": revision,
        "depends_on": depends_on,
        "description": f"migration {revision}",
        "upgrade": upgrade,
    })


def _patch(migrations: dict):
    return patch("delembic.executor.load_migrations", return_value=migrations)


def test_no_migrations(tmp_path, capsys):
    with _patch({}):
        run_upgrade(_engine(), tmp_path)
    assert "No migrations found" in capsys.readouterr().out


def test_runs_all_pending(tmp_path):
    m1 = _make("D001")
    m2 = _make("D002", ["D001"])
    engine = _engine()
    with _patch({"D001": m1, "D002": m2}):
        run_upgrade(engine, tmp_path)
    with engine.connect() as conn:
        ensure_tables(conn)
        assert get_applied(conn) == {"D001", "D002"}


def test_skips_already_applied(tmp_path):
    m1 = _make("D001")
    m2 = _make("D002", ["D001"])
    engine = _engine()

    # Apply D001 first
    with _patch({"D001": m1}):
        run_upgrade(engine, tmp_path)

    # Now run with both — only D002 should run
    ran = []
    original_upgrade = m2.upgrade

    def tracked_upgrade(self, conn):
        ran.append("D002")

    m2.upgrade = tracked_upgrade

    with _patch({"D001": m1, "D002": m2}):
        run_upgrade(engine, tmp_path)

    assert ran == ["D002"]


def test_already_up_to_date(tmp_path, capsys):
    m1 = _make("D001")
    engine = _engine()
    with _patch({"D001": m1}):
        run_upgrade(engine, tmp_path)
        capsys.readouterr()
        run_upgrade(engine, tmp_path)
    assert "Already up to date" in capsys.readouterr().out


def test_stops_on_failure(tmp_path):
    m1 = _make("D001", fail=True)
    m2 = _make("D002", ["D001"])
    engine = _engine()
    with _patch({"D001": m1, "D002": m2}):
        with pytest.raises(SystemExit):
            run_upgrade(engine, tmp_path)
    with engine.connect() as conn:
        ensure_tables(conn)
        # D001 failed, D002 never ran
        assert get_applied(conn) == set()


def test_failed_migration_recorded(tmp_path):
    from delembic.db import version_table
    m1 = _make("D001", fail=True)
    # Use file-based SQLite so meta_conn commits survive after run_upgrade exits
    engine = sa.create_engine(f"sqlite:///{tmp_path}/test.db")
    with _patch({"D001": m1}):
        with pytest.raises(SystemExit):
            run_upgrade(engine, tmp_path)
    with engine.connect() as conn:
        ensure_tables(conn)
        row = conn.execute(
            sa.select(version_table.c.status).where(version_table.c.revision == "D001")
        ).fetchone()
    assert row[0] == "failed"


def test_target_revision_limits_run(tmp_path):
    m1 = _make("D001")
    m2 = _make("D002", ["D001"])
    m3 = _make("D003", ["D002"])
    engine = _engine()
    with _patch({"D001": m1, "D002": m2, "D003": m3}):
        run_upgrade(engine, tmp_path, target="D002")
    with engine.connect() as conn:
        ensure_tables(conn)
        applied = get_applied(conn)
    assert "D001" in applied
    assert "D002" in applied
    assert "D003" not in applied


def test_external_dep_without_alembic_config_raises(tmp_path):
    m1 = _make("D001", depends_on=["abc123alembic"])
    with _patch({"D001": m1}):
        with pytest.raises(SystemExit):
            run_upgrade(_engine(), tmp_path, alembic_ini=None)


def test_external_dep_satisfied_proceeds(tmp_path):
    m1 = _make("D001", depends_on=["abc123alembic"])
    engine = _engine()
    fake_ini = tmp_path / "alembic.ini"
    fake_ini.touch()

    with _patch({"D001": m1}):
        with patch(
            "delembic.executor.check_alembic_deps",
            return_value=None,
        ):
            run_upgrade(engine, tmp_path, alembic_ini=fake_ini)

    with engine.connect() as conn:
        ensure_tables(conn)
        assert get_applied(conn) == {"D001"}


def test_external_dep_missing_raises(tmp_path):
    from delembic.alembic_compat import AlembicDepsError
    m1 = _make("D001", depends_on=["abc123alembic"])
    fake_ini = tmp_path / "alembic.ini"
    fake_ini.touch()

    with _patch({"D001": m1}):
        with patch(
            "delembic.executor.check_alembic_deps",
            side_effect=AlembicDepsError("Alembic revision abc123alembic not applied"),
        ):
            with pytest.raises(SystemExit):
                run_upgrade(_engine(), tmp_path, alembic_ini=fake_ini)
