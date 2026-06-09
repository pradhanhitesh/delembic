import importlib.util
import sys
from pathlib import Path
from typing import Type

from delembic.migration import DataMigration


def load_migrations(versions_dir: Path) -> dict[str, Type[DataMigration]]:
    migrations: dict[str, Type[DataMigration]] = {}

    project_root = str(versions_dir.parent.parent.resolve())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    for path in sorted(versions_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue

        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, DataMigration)
                and obj is not DataMigration
                and hasattr(obj, "revision")
            ):
                migrations[obj.revision] = obj

    return migrations
