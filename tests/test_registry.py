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
