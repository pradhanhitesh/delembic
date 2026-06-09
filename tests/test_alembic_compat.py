from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa

from delembic.alembic_compat import (
    AlembicDepsError,
    check_alembic_deps,
    get_alembic_applied_revisions,
    get_current_heads,
)


@pytest.fixture
def sqlite_conn():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        yield conn


def _mock_migration_context(heads: tuple[str, ...]):
    ctx = MagicMock()
    ctx.get_current_heads.return_value = heads
    return ctx


def test_get_current_heads_empty_db(sqlite_conn):
    # Fresh SQLite DB — no alembic_version table → Alembic returns no heads
    heads = get_current_heads(sqlite_conn)
    assert heads == []


def test_get_current_heads_returns_list(sqlite_conn):
    with patch("alembic.runtime.migration.MigrationContext.configure") as mock_cfg:
        mock_cfg.return_value = _mock_migration_context(("abc123", "def456"))
        heads = get_current_heads(sqlite_conn)
    assert set(heads) == {"abc123", "def456"}


def test_get_current_heads_import_error(sqlite_conn):
    import sys
    original = sys.modules.pop("alembic.runtime.migration", None)
    try:
        with patch.dict("sys.modules", {"alembic.runtime.migration": None}):
            with pytest.raises(AlembicDepsError, match="alembic package not installed"):
                get_current_heads(sqlite_conn)
    finally:
        if original is not None:
            sys.modules["alembic.runtime.migration"] = original


def test_check_alembic_deps_passes(sqlite_conn, tmp_path):
    with patch("delembic.alembic_compat.get_alembic_applied_revisions", return_value={"abc123", "def456"}):
        check_alembic_deps(sqlite_conn, tmp_path / "alembic.ini", ["abc123"], "D001")


def test_check_alembic_deps_fails_missing(sqlite_conn, tmp_path):
    with patch("delembic.alembic_compat.get_alembic_applied_revisions", return_value={"abc123"}):
        with pytest.raises(AlembicDepsError, match="def456"):
            check_alembic_deps(sqlite_conn, tmp_path / "alembic.ini", ["abc123", "def456"], "D001")


def test_check_alembic_deps_error_mentions_migration(sqlite_conn, tmp_path):
    with patch("delembic.alembic_compat.get_alembic_applied_revisions", return_value=set()):
        with pytest.raises(AlembicDepsError, match="D001"):
            check_alembic_deps(sqlite_conn, tmp_path / "alembic.ini", ["abc123"], "D001")


def test_get_alembic_applied_revisions_walks_history(sqlite_conn, tmp_path):
    fake_rev_a = MagicMock(); fake_rev_a.revision = "aaa111"
    fake_rev_b = MagicMock(); fake_rev_b.revision = "bbb222"

    mock_script = MagicMock()
    mock_script.iterate_revisions.return_value = [fake_rev_a, fake_rev_b]

    mock_ctx = _mock_migration_context(("aaa111",))

    with patch("alembic.config.Config"), \
         patch("alembic.script.ScriptDirectory.from_config", return_value=mock_script), \
         patch("alembic.runtime.migration.MigrationContext.configure", return_value=mock_ctx):
        applied = get_alembic_applied_revisions(sqlite_conn, tmp_path / "alembic.ini")

    assert applied == {"aaa111", "bbb222"}


def test_get_alembic_applied_revisions_no_heads(sqlite_conn, tmp_path):
    mock_script = MagicMock()
    mock_ctx = _mock_migration_context(())  # no heads applied

    with patch("alembic.config.Config"), \
         patch("alembic.script.ScriptDirectory.from_config", return_value=mock_script), \
         patch("alembic.runtime.migration.MigrationContext.configure", return_value=mock_ctx):
        applied = get_alembic_applied_revisions(sqlite_conn, tmp_path / "alembic.ini")

    assert applied == set()
    mock_script.iterate_revisions.assert_not_called()
