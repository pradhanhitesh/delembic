from pathlib import Path

import pytest

from delembic.config import Config, find_config


def _write_multi_section_ini(path: Path) -> None:
    path.write_text(
        "[delembic]\n"
        "script_location = bronze\n"
        "sqlalchemy.url = sqlite:///bronze.db\n"
        "\n"
        "[silver]\n"
        "script_location = silver\n"
        "sqlalchemy.url = sqlite:///silver.db\n"
    )


def test_config_defaults_to_delembic_section(tmp_path):
    ini = tmp_path / "delembic.ini"
    _write_multi_section_ini(ini)
    cfg = Config(ini)
    assert cfg.section == "delembic"
    assert cfg.url == "sqlite:///bronze.db"
    assert cfg.script_location == Path("bronze")


def test_config_reads_named_section(tmp_path):
    ini = tmp_path / "delembic.ini"
    _write_multi_section_ini(ini)
    cfg = Config(ini, section="silver")
    assert cfg.section == "silver"
    assert cfg.url == "sqlite:///silver.db"
    assert cfg.script_location == Path("silver")


def test_config_missing_named_section_raises(tmp_path):
    ini = tmp_path / "delembic.ini"
    _write_multi_section_ini(ini)
    with pytest.raises(FileNotFoundError, match=r"\[gold\]"):
        Config(ini, section="gold")


def test_config_versions_dir_is_section_scoped(tmp_path):
    ini = tmp_path / "delembic.ini"
    _write_multi_section_ini(ini)
    bronze = Config(ini, section="delembic")
    silver = Config(ini, section="silver")
    assert bronze.versions_dir == tmp_path / "bronze" / "versions"
    assert silver.versions_dir == tmp_path / "silver" / "versions"


def test_find_config_walks_up_cwd(tmp_path, monkeypatch):
    ini = tmp_path / "delembic.ini"
    _write_multi_section_ini(ini)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    cfg = find_config()
    assert cfg.ini_path == ini.resolve()


def test_find_config_missing_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="delembic.ini not found"):
        find_config()


def test_find_config_with_explicit_path_and_section(tmp_path):
    ini = tmp_path / "other.ini"
    _write_multi_section_ini(ini)
    cfg = find_config(ini_path=ini, section="silver")
    assert cfg.section == "silver"
    assert cfg.url == "sqlite:///silver.db"


def test_find_config_explicit_path_missing_raises(tmp_path):
    missing = tmp_path / "nope.ini"
    with pytest.raises(FileNotFoundError, match="nope.ini"):
        find_config(ini_path=missing)
