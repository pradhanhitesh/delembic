import re
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from delembic.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def project(tmp_path):
    """Temp dir with delembic.ini and versions/ already set up."""
    ini = tmp_path / "delembic.ini"
    ini.write_text(
        "[delembic]\n"
        "script_location = delembic\n"
        "sqlalchemy.url = sqlite:///:memory:\n"
    )
    (tmp_path / "delembic" / "versions").mkdir(parents=True)
    return tmp_path


# --- init ---

def test_init_creates_files(runner):
    with runner.isolated_filesystem() as td:
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        assert Path(td, "delembic.ini").exists()
        assert Path(td, "delembic", "env.py").exists()
        assert Path(td, "delembic", "versions").is_dir()


def test_init_custom_directory(runner):
    with runner.isolated_filesystem() as td:
        result = runner.invoke(cli, ["init", "data-migrations"])
        assert result.exit_code == 0
        assert "script_location = data-migrations" in Path(td, "delembic.ini").read_text()
        assert Path(td, "data-migrations", "versions").is_dir()


def test_init_fails_if_already_exists(tmp_path, runner):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["init"])
    assert result.exit_code != 0
    assert "already exists" in result.output


# --- revision ---

def test_revision_generates_file(project, runner):
    with runner.isolated_filesystem(temp_dir=project):
        result = runner.invoke(cli, ["revision", "-m", "load vocabulary"])
    assert result.exit_code == 0
    versions = list((project / "delembic" / "versions").glob("*.py"))
    assert len(versions) == 1
    content = versions[0].read_text()
    assert re.search(r'revision = "[0-9a-f]{12}"', content)
    assert 'description = "load vocabulary"' in content


def test_revision_increments_id(project, runner):
    with runner.isolated_filesystem(temp_dir=project):
        runner.invoke(cli, ["revision", "-m", "first"])
        runner.invoke(cli, ["revision", "-m", "second"])
    versions = sorted((project / "delembic" / "versions").glob("*.py"))
    assert len(versions) == 2
    # each file embeds a unique 12-char hex revision ID
    revision_ids = set()
    for v in versions:
        m = re.search(r'revision = "([0-9a-f]{12})"', v.read_text())
        assert m, f"no revision ID found in {v.name}"
        revision_ids.add(m.group(1))
    assert len(revision_ids) == 2


def test_revision_class_name_from_message(project, runner):
    with runner.isolated_filesystem(temp_dir=project):
        runner.invoke(cli, ["revision", "-m", "load person table"])
    versions = list((project / "delembic" / "versions").glob("*.py"))
    content = versions[0].read_text()
    assert "class LoadPersonTable" in content


def test_revision_captures_alembic_heads(project, runner):
    # Overwrite ini with file-based SQLite + alembic_config
    (project / "delembic.ini").write_text(
        "[delembic]\n"
        "script_location = delembic\n"
        f"sqlalchemy.url = sqlite:///{project}/test.db\n"
        "alembic_config = alembic.ini\n"
    )
    with patch("delembic.alembic_compat.get_current_heads", return_value=["abc123def456"]):
        with runner.isolated_filesystem(temp_dir=project):
            result = runner.invoke(cli, ["revision", "-m", "load vocab"])
    assert result.exit_code == 0, result.output
    versions = list((project / "delembic" / "versions").glob("*.py"))
    assert versions, "revision file not created"
    content = versions[0].read_text()
    assert "abc123def456" in content
    assert "Alembic heads captured" in result.output


def test_revision_no_alembic_config_empty_depends_on(project, runner):
    with runner.isolated_filesystem(temp_dir=project):
        runner.invoke(cli, ["revision", "-m", "load vocab"])
    versions = list((project / "delembic" / "versions").glob("*.py"))
    content = versions[0].read_text()
    assert "depends_on = []" in content


# --- upgrade ---

def test_upgrade_no_migrations(project, runner):
    with runner.isolated_filesystem(temp_dir=project):
        result = runner.invoke(cli, ["upgrade", "head"])
    assert result.exit_code == 0
    assert "No migrations found" in result.output


def test_upgrade_runs_migration(project, runner):
    (project / "delembic" / "versions" / "D001_load_vocab.py").write_text(
        "from delembic import DataMigration\n"
        "class LoadVocab(DataMigration):\n"
        "    revision = 'D001'\n"
        "    depends_on = []\n"
        "    description = 'load vocab'\n"
        "    def upgrade(self, conn): pass\n"
    )
    with runner.isolated_filesystem(temp_dir=project):
        result = runner.invoke(cli, ["upgrade", "head"])
    assert result.exit_code == 0
    assert "OK" in result.output


# --- current ---

def test_current_no_migrations(project, runner):
    with runner.isolated_filesystem(temp_dir=project):
        result = runner.invoke(cli, ["current"])
    assert result.exit_code == 0
    assert "No migrations applied" in result.output


# --- history ---

def test_history_no_migrations(project, runner):
    with runner.isolated_filesystem(temp_dir=project):
        result = runner.invoke(cli, ["history"])
    assert result.exit_code == 0
    assert "No migrations found" in result.output


# --- multi-section (-n / -c) ---

def test_init_adds_named_section_to_existing_ini(runner):
    with runner.isolated_filesystem() as td:
        result = runner.invoke(cli, ["init", "bronze"])
        assert result.exit_code == 0, result.output
        result = runner.invoke(cli, ["-n", "silver", "init", "silver"])
        assert result.exit_code == 0, result.output
        ini_text = Path(td, "delembic.ini").read_text()
        assert "[delembic]" in ini_text
        assert "[silver]" in ini_text
        assert "script_location = silver" in ini_text
        assert Path(td, "silver", "versions").is_dir()


def test_init_named_section_already_exists_fails(runner):
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "bronze"])
        # default section already present -> plain re-init fails
        result = runner.invoke(cli, ["init", "bronze2"])
        assert result.exit_code != 0
        assert "already exists" in result.output
        # explicit -n delembic hits the same already-present section
        result = runner.invoke(cli, ["-n", "delembic", "init", "bronze3"])
        assert result.exit_code != 0
        assert "already exists" in result.output


def test_init_named_section_without_existing_ini_fails(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["-n", "silver", "init", "silver"])
        assert result.exit_code != 0
        assert "does not exist yet" in result.output


def test_name_option_dispatches_to_named_section(runner):
    with runner.isolated_filesystem() as td:
        td = Path(td)
        runner.invoke(cli, ["init", "bronze"])
        runner.invoke(cli, ["-n", "silver", "init", "silver"])
        (td / "delembic.ini").write_text(
            "[delembic]\n"
            "script_location = bronze\n"
            "sqlalchemy.url = sqlite:///:memory:\n"
            "\n"
            "[silver]\n"
            "script_location = silver\n"
            "sqlalchemy.url = sqlite:///:memory:\n"
        )
        result = runner.invoke(cli, ["-n", "silver", "revision", "-m", "add col"])
        assert result.exit_code == 0, result.output
        assert list((td / "silver" / "versions").glob("*.py"))
        assert not list((td / "bronze" / "versions").glob("*.py"))


def test_unknown_section_fails(runner):
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "bronze"])
        result = runner.invoke(cli, ["-n", "gold", "current"])
        assert result.exit_code != 0
        assert "gold" in result.output


def test_config_option_points_to_alternate_ini(runner, tmp_path):
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    other_ini = other_dir / "gold.ini"
    other_ini.write_text(
        "[delembic]\n"
        "script_location = gold\n"
        f"sqlalchemy.url = sqlite:///{other_dir}/gold.db\n"
    )
    (other_dir / "gold" / "versions").mkdir(parents=True)

    with runner.isolated_filesystem():
        # no delembic.ini here at all — must resolve purely via -c
        result = runner.invoke(cli, ["-c", str(other_ini), "revision", "-m", "add col"])
        assert result.exit_code == 0, result.output
        assert list((other_dir / "gold" / "versions").glob("*.py"))


def test_history_imports_project_root_with_nested_script_location(runner):
    """Regression: script_location nested under a shared 'delembic/' folder
    (e.g. multi-section bronze/silver/gold layout) must still put the real
    project root — not one level short of it — on sys.path so migration
    files can import sibling project packages."""
    with runner.isolated_filesystem() as td:
        td = Path(td)
        (td / "mypkg").mkdir()
        (td / "mypkg" / "__init__.py").write_text("VALUE = 42\n")

        versions_dir = td / "delembic" / "bronze" / "versions"
        versions_dir.mkdir(parents=True)
        (td / "delembic.ini").write_text(
            "[delembic]\n"
            "script_location = delembic/bronze\n"
            "sqlalchemy.url = sqlite:///:memory:\n"
        )
        (versions_dir / "D001_uses_project_root.py").write_text(
            "import mypkg\n"
            "from delembic import DataMigration\n"
            "class UsesRoot(DataMigration):\n"
            "    revision = 'D001'\n"
            "    depends_on = []\n"
            "    description = 'uses project root, value=' + str(mypkg.VALUE)\n"
            "    def upgrade(self, conn): pass\n"
        )
        result = runner.invoke(cli, ["history"])
    assert result.exit_code == 0, result.output
    assert "D001" in result.output
    assert "value=42" in result.output


def test_history_shows_status(runner):
    # Use file-based SQLite so state persists across CLI invocations
    with runner.isolated_filesystem() as td:
        td = Path(td)
        (td / "delembic" / "versions").mkdir(parents=True)
        (td / "delembic.ini").write_text(
            "[delembic]\n"
            "script_location = delembic\n"
            f"sqlalchemy.url = sqlite:///{td}/test.db\n"
        )
        (td / "delembic" / "versions" / "D001_load_vocab.py").write_text(
            "from delembic import DataMigration\n"
            "class LoadVocab(DataMigration):\n"
            "    revision = 'D001'\n"
            "    depends_on = []\n"
            "    description = 'load vocab'\n"
            "    def upgrade(self, conn): pass\n"
        )
        runner.invoke(cli, ["upgrade", "head"])
        result = runner.invoke(cli, ["history"])
    assert "applied" in result.output
    assert "D001" in result.output
