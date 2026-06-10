import configparser
import importlib.util
from pathlib import Path

import sqlalchemy as sa


class Config:
    def __init__(self, ini_path: Path):
        self.ini_path = ini_path.resolve()
        cp = configparser.RawConfigParser()
        cp.read(self.ini_path)
        self.script_location = Path(cp.get("delembic", "script_location", fallback="delembic"))
        self.url = cp.get("delembic", "sqlalchemy.url", fallback="")
        self.filename_template: str = cp.get(
            "delembic",
            "filename_template",
            fallback="%(year)s_%(month)s_%(day)s_%(hour)s%(minute)s%(second)s_%(revision)s_%(slug)s",
        )
        _alembic_raw = cp.get("delembic", "alembic_config", fallback="")
        self.alembic_config: Path | None = (
            (self.ini_path.parent / _alembic_raw) if _alembic_raw else None
        )

    @property
    def versions_dir(self) -> Path:
        return self.ini_path.parent / self.script_location / "versions"

    @property
    def env_py(self) -> Path:
        return self.ini_path.parent / self.script_location / "env.py"

    def engine(self) -> sa.Engine:
        if self.url:
            return sa.create_engine(self.url)
        return self._engine_from_env_py()

    def _engine_from_env_py(self) -> sa.Engine:
        if not self.env_py.exists():
            raise RuntimeError(
                "sqlalchemy.url not set in delembic.ini and no env.py found. "
                f"Expected: {self.env_py}"
            )
        spec = importlib.util.spec_from_file_location("delembic_env", self.env_py)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load env.py: {self.env_py}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        if not hasattr(module, "get_engine"):
            raise RuntimeError(
                f"env.py must define a get_engine() function: {self.env_py}"
            )
        return module.get_engine()


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
