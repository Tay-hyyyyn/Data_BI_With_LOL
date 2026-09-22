from __future__ import annotations

import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

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


def test_a_failed_backup_leaves_no_file_at_the_final_path(tmp_path, monkeypatch) -> None:
    """Regression: create_backup used to write the zip directly to `output`, so a crash partway
    through left a truncated-but-present archive at the final path instead of nothing."""
    backup = load_script("backup_data")
    data_root = tmp_path / "data"
    data_root.mkdir()
    with sqlite3.connect(data_root / "metadata.db") as connection:
        connection.execute("CREATE TABLE datasets(id TEXT PRIMARY KEY)")
    output = tmp_path / "backup.zip"

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated crash mid-backup")

    monkeypatch.setattr(backup, "add_tree", boom)

    with pytest.raises(RuntimeError, match="simulated crash"):
        backup.create_backup(data_root, output)

    assert not output.exists()
    assert list(tmp_path.glob("*.tmp")) == []  # the temp file is cleaned up too, not left behind


def test_verify_backup_rejects_a_tampered_file(tmp_path) -> None:
    backup = load_script("backup_data")
    verify = load_script("verify_backup")
    data_root = tmp_path / "data"
    data_root.mkdir()
    with sqlite3.connect(data_root / "metadata.db") as connection:
        connection.execute("CREATE TABLE datasets(id TEXT PRIMARY KEY)")
    published = data_root / "published" / "dataset-1" / "version-1"
    published.mkdir(parents=True)
    (published / "data.parquet").write_bytes(b"original bytes")
    archive_path = backup.create_backup(data_root, tmp_path / "backup.zip")

    # Rewrite one entry's bytes in place without touching the recorded manifest checksum.
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(tampered, "w") as destination:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.endswith("data.parquet"):
                data = b"tampered bytes!!"
            destination.writestr(item, data)

    with pytest.raises(ValueError, match="무결성"):
        verify.verify_backup(tampered)


def test_verify_backup_rejects_path_traversal_in_the_manifest(tmp_path) -> None:
    verify = load_script("verify_backup")
    archive_path = tmp_path / "hostile.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "backup-manifest.json",
            json.dumps({"format": "data-bi-backup-v1", "includes_raw": False, "files": [{"path": "../../etc/passwd", "sha256": "x"}]}),
        )
        archive.writestr("../../etc/passwd", "not actually escaping")

    with pytest.raises(ValueError, match="안전하지 않은"):
        verify.verify_backup(archive_path)


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
