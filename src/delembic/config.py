import configparser
from pathlib import Path

import sqlalchemy as sa


class Config:
    def __init__(self, ini_path: Path):
        self.ini_path = ini_path.resolve()
        cp = configparser.ConfigParser()
        cp.read(self.ini_path)
        self.script_location = Path(cp.get("delembic", "script_location", fallback="delembic"))
        self.url = cp.get("delembic", "sqlalchemy.url", fallback="")
        _alembic_raw = cp.get("delembic", "alembic_config", fallback="")
        self.alembic_config: Path | None = (
            (self.ini_path.parent / _alembic_raw) if _alembic_raw else None
        )

    @property
    def versions_dir(self) -> Path:
        return self.ini_path.parent / self.script_location / "versions"

    def engine(self) -> sa.Engine:
        if not self.url:
            raise RuntimeError("sqlalchemy.url not set in delembic.ini")
        return sa.create_engine(self.url)


def find_config() -> Config:
    """Walk up from cwd looking for delembic.ini."""
    cwd = Path.cwd()
    for directory in [cwd, *cwd.parents]:
        candidate = directory / "delembic.ini"
        if candidate.exists():
            return Config(candidate)
    raise FileNotFoundError(
        "delembic.ini not found. Run 'delembic init' first."
    )
