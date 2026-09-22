"""Create a portable, integrity-checked backup of the local BI state.

Published Parquet and a SQLite online backup are always included. Raw uploads and
private Riot bronze payloads require ``--include-raw`` because they can be large
and may contain source-restricted data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_sqlite_online(source: Path, destination: Path) -> None:
    """Copy a consistent SQLite snapshot even when WAL mode is enabled."""
    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def add_tree(archive: zipfile.ZipFile, root: Path, relative_root: str, entries: list[dict[str, str]]) -> None:
    if not root.exists():
        return
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = Path(relative_root) / path.relative_to(root)
        archive.write(path, relative.as_posix())
        entries.append({"path": relative.as_posix(), "sha256": sha256(path)})


def create_backup(data_root: Path, output: Path, include_raw: bool = False) -> Path:
    data_root = data_root.resolve()
    metadata = data_root / "metadata.db"
    if not metadata.is_file():
        raise FileNotFoundError(f"메타데이터 DB를 찾을 수 없습니다: {metadata}")
    output.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []
    # Build the archive at a temporary path in the same directory and rename it into place only
    # once it is complete. Writing straight to `output` would leave a truncated-but-present file
    # at the final path if the process is interrupted mid-write, which `verify_backup` would only
    # catch if someone remembered to run it.
    with tempfile.TemporaryDirectory(prefix="data-bi-backup-") as temp:
        temp_metadata = Path(temp) / "metadata.db"
        copy_sqlite_online(metadata, temp_metadata)
        temp_output = output.parent / f"{output.name}.tmp"
        try:
            with zipfile.ZipFile(temp_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(temp_metadata, "metadata.db")
                entries.append({"path": "metadata.db", "sha256": sha256(temp_metadata)})
                add_tree(archive, data_root / "published", "published", entries)
                if include_raw:
                    add_tree(archive, data_root / "raw", "raw", entries)
                    add_tree(archive, data_root / "bronze", "bronze", entries)
                manifest = {
                    "format": "data-bi-backup-v1",
                    "created_at": datetime.now(UTC).isoformat(),
                    "includes_raw": include_raw,
                    "files": entries,
                }
                archive.writestr("backup-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            os.replace(temp_output, output)
        except BaseException:
            temp_output.unlink(missing_ok=True)
            raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up local Data BI metadata and published Parquet.")
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "backups" / f"data-bi-{datetime.now():%Y%m%d-%H%M%S}.zip")
    parser.add_argument("--include-raw", action="store_true", help="Include raw uploads and private Riot bronze payloads.")
    args = parser.parse_args()
    path = create_backup(args.data_root, args.output, args.include_raw)
    print(path)


if __name__ == "__main__":
    main()
