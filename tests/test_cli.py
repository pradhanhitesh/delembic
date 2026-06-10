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
