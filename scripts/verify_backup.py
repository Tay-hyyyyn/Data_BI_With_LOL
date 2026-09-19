"""Validate a Data BI backup archive without modifying any local data."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_backup(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("backup-manifest.json"))
        if manifest.get("format") != "data-bi-backup-v1":
            raise ValueError("지원하지 않는 백업 형식입니다.")
        for item in manifest.get("files", []):
            path = item["path"]
            if Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("안전하지 않은 백업 경로입니다.")
            if digest(archive.read(path)) != item["sha256"]:
                raise ValueError(f"무결성 검증 실패: {path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a Data BI backup archive.")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    manifest = verify_backup(args.archive)
    print(f"verified {len(manifest['files'])} files; includes_raw={manifest['includes_raw']}")


if __name__ == "__main__":
    main()
