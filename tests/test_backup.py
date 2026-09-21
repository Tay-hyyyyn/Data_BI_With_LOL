from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_contains_consistent_metadata_and_published_parquet(tmp_path) -> None:
    backup = load_script("backup_data")
    verify = load_script("verify_backup")
    data_root = tmp_path / "data"
    data_root.mkdir()
    with sqlite3.connect(data_root / "metadata.db") as connection:
        connection.execute("CREATE TABLE datasets(id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO datasets VALUES ('dataset-1')")
    published = data_root / "published" / "dataset-1" / "version-1"
    published.mkdir(parents=True)
    (published / "manifest.json").write_text('{"complete": true}', encoding="utf-8")
    (published / "data.parquet").write_bytes(b"parquet")
    (data_root / "bronze").mkdir()
    (data_root / "bronze" / "private.json").write_text("private", encoding="utf-8")

    archive = backup.create_backup(data_root, tmp_path / "backup.zip")
    manifest = verify.verify_backup(archive)

    assert manifest["includes_raw"] is False
    assert {item["path"] for item in manifest["files"]} == {
        "metadata.db", "published/dataset-1/version-1/manifest.json", "published/dataset-1/version-1/data.parquet"
    }


def test_restore_requires_empty_target_and_recovers_published_data(tmp_path) -> None:
    backup = load_script("backup_data")
    restore = load_script("restore_data")
    data_root = tmp_path / "source"
    data_root.mkdir()
    with sqlite3.connect(data_root / "metadata.db") as connection:
        connection.execute("CREATE TABLE datasets(id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO datasets VALUES ('dataset-1')")
    source_file = data_root / "published" / "dataset-1" / "version-1" / "data.parquet"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"parquet")
    archive = backup.create_backup(data_root, tmp_path / "backup.zip")

    restored = restore.restore_backup(archive, tmp_path / "restored")

    assert (restored / "metadata.db").is_file()
    assert (restored / "published" / "dataset-1" / "version-1" / "data.parquet").read_bytes() == b"parquet"
