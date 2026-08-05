import sys

import pytest

from delembic.registry import load_migrations


_MIGRATION_SRC = """\
from delembic import DataMigration

class LoadVocabulary(DataMigration):
    revision = "D001"
    depends_on = []
    description = "load vocabulary"
    def upgrade(self, conn): pass
"""

_MIGRATION_SRC_2 = """\
from delembic import DataMigration

class LoadPerson(DataMigration):
    revision = "D002"
    depends_on = ["D001"]
    description = "load person"
    def upgrade(self, conn): pass
"""


def test_empty_directory(tmp_path):
    assert load_migrations(tmp_path) == {}


def test_loads_single_migration(tmp_path):
    (tmp_path / "D001_load_vocabulary.py").write_text(_MIGRATION_SRC)
    migrations = load_migrations(tmp_path)
    assert "D001" in migrations
    assert migrations["D001"].description == "load vocabulary"


def test_loads_multiple_migrations(tmp_path):
    (tmp_path / "D001_load_vocabulary.py").write_text(_MIGRATION_SRC)
    (tmp_path / "D002_load_person.py").write_text(_MIGRATION_SRC_2)
    migrations = load_migrations(tmp_path)
    assert set(migrations.keys()) == {"D001", "D002"}


def test_ignores_dunder_files(tmp_path):
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "_private.py").write_text("")
    (tmp_path / "D001_load_vocabulary.py").write_text(_MIGRATION_SRC)
    migrations = load_migrations(tmp_path)
    assert list(migrations.keys()) == ["D001"]


def test_depends_on_preserved(tmp_path):
    (tmp_path / "D002_load_person.py").write_text(_MIGRATION_SRC_2)
    migrations = load_migrations(tmp_path)
    assert migrations["D002"].depends_on == ["D001"]


def test_migration_is_instantiable(tmp_path):
    (tmp_path / "D001_load_vocabulary.py").write_text(_MIGRATION_SRC)
    migrations = load_migrations(tmp_path)
    instance = migrations["D001"]()
    assert instance.revision == "D001"


# --- project_root resolution ---
# Regression: a naive versions_dir.parent.parent guess breaks once script_location
# is nested more than one level deep (e.g. "delembic/bronze/versions" under a
# multi-section layout) — it lands one level short of the real project root.

def test_default_project_root_matches_flat_layout(tmp_path):
    """script_location/versions -> parent.parent is the project root (unchanged default)."""
    versions_dir = tmp_path / "delembic" / "versions"
    versions_dir.mkdir(parents=True)
    root = str(tmp_path.resolve())
    try:
        load_migrations(versions_dir)
        assert root in sys.path
    finally:
        if root in sys.path:
            sys.path.remove(root)


def test_explicit_project_root_used_for_nested_layout(tmp_path):
    """With script_location nested two levels deep, parent.parent would be wrong —
    passing project_root explicitly must be what lands on sys.path."""
    versions_dir = tmp_path / "delembic" / "bronze" / "versions"
    versions_dir.mkdir(parents=True)
    root = str(tmp_path.resolve())
    wrong_root = str(versions_dir.parent.parent.resolve())  # == tmp_path/delembic
    assert wrong_root != root
    try:
        load_migrations(versions_dir, project_root=tmp_path)
        assert root in sys.path
        assert wrong_root not in sys.path
    finally:
        if root in sys.path:
            sys.path.remove(root)
