from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from delembic.db import ensure_tables, get_applied, history_table, record_result, version_table


@pytest.fixture
def conn():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as c:
        ensure_tables(c)
        c.commit()
        yield c


def test_ensure_tables_creates_version_table(conn):
    result = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = {row[0] for row in result}
    assert "delembic_version" in tables
    assert "delembic_run_history" in tables


def test_ensure_tables_idempotent(conn):
    ensure_tables(conn)  # second call should not raise
    conn.commit()


def test_get_applied_empty(conn):
    assert get_applied(conn) == set()


def _now():
    return datetime.now(timezone.utc)


def test_record_result_success(conn):
    t = _now()
    record_result(conn, "D001", t, t, 1.5, "success")
    conn.commit()
    assert get_applied(conn) == {"D001"}


def test_record_result_failed_not_in_applied(conn):
    t = _now()
    record_result(conn, "D001", t, t, 0.1, "failed", exception="oops")
    conn.commit()
    assert get_applied(conn) == set()


def test_record_result_retry_replaces_previous(conn):
    t = _now()
    record_result(conn, "D001", t, t, 0.1, "failed")
    record_result(conn, "D001", t, t, 0.2, "success")
    conn.commit()
    assert get_applied(conn) == {"D001"}
    row = conn.execute(
        sa.select(version_table.c.status).where(version_table.c.revision == "D001")
    ).fetchone()
    assert row[0] == "success"


def test_history_table_appends_on_retry(conn):
    t = _now()
    record_result(conn, "D001", t, t, 0.1, "failed")
    record_result(conn, "D001", t, t, 0.2, "success")
    conn.commit()
    rows = conn.execute(
        sa.select(history_table.c.status).where(history_table.c.revision == "D001")
    ).fetchall()
    statuses = [r[0] for r in rows]
    assert "failed" in statuses
    assert "success" in statuses


def test_get_applied_multiple(conn):
    t = _now()
    record_result(conn, "D001", t, t, 1.0, "success")
    record_result(conn, "D002", t, t, 2.0, "success")
    record_result(conn, "D003", t, t, 0.5, "failed")
    conn.commit()
    assert get_applied(conn) == {"D001", "D002"}
