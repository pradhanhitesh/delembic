from datetime import datetime, timezone

import sqlalchemy as sa

_metadata = sa.MetaData()

version_table = sa.Table(
    "delembic_version",
    _metadata,
    sa.Column("revision", sa.Text, primary_key=True),
    sa.Column("applied_at", sa.DateTime(timezone=True)),
    sa.Column("status", sa.Text),
    sa.Column("execution_time_seconds", sa.Float),
)

history_table = sa.Table(
    "delembic_run_history",
    _metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("revision", sa.Text),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("ended_at", sa.DateTime(timezone=True)),
    sa.Column("duration_seconds", sa.Float),
    sa.Column("status", sa.Text),
    sa.Column("exception", sa.Text),
    sa.Column("username", sa.Text),
    sa.Column("hostname", sa.Text),
)


def ensure_tables(conn: sa.Connection) -> None:
    _metadata.create_all(conn, checkfirst=True)


def get_applied(conn: sa.Connection) -> set[str]:
    rows = conn.execute(
        sa.select(version_table.c.revision).where(version_table.c.status == "success")
    )
    return {row[0] for row in rows}


def record_result(
    conn: sa.Connection,
    revision: str,
    started_at: datetime,
    ended_at: datetime,
    duration: float,
    status: str,
    exception: str | None = None,
    username: str | None = None,
    hostname: str | None = None,
) -> None:
    conn.execute(
        sa.delete(version_table).where(version_table.c.revision == revision)
    )
    conn.execute(
        sa.insert(version_table).values(
            revision=revision,
            applied_at=ended_at,
            status=status,
            execution_time_seconds=duration,
        )
    )
    conn.execute(
        sa.insert(history_table).values(
            revision=revision,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration,
            status=status,
            exception=exception,
            username=username,
            hostname=hostname,
        )
    )
