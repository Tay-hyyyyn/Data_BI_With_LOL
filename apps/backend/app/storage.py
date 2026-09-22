from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .config import settings


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_uploaded_file(path: Path, suffix: str, sheet_name: str | None = None) -> pd.DataFrame:
    suffix = suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="cp949")
    if suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=sheet_name or 0)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError("CSV, XLSX, Parquet 파일만 지원합니다.")


def publish_dataframe(dataset_id: str, version_id: str, frame: pd.DataFrame) -> dict:
    staging_root = settings.root / "staging" / version_id
    published_root = settings.root / "published" / dataset_id / version_id
    # `version_id` is a fresh UUID per call, so a collision here almost never happens by chance —
    # it means a previous crash left this exact staging directory behind. Tolerate and overwrite
    # it rather than failing the publish permanently; `cleanup_staging()` also sweeps these on
    # startup so they do not accumulate.
    staging_root.mkdir(parents=True, exist_ok=True)
    parquet_path = staging_root / "part-00000.parquet"
    frame.to_parquet(parquet_path, index=False, compression="zstd", row_group_size=122_880)
    body_hash = sha256_file(parquet_path)
    manifest = {
        "dataset_id": dataset_id,
        "version_id": version_id,
        "created_at": utcnow(),
        "row_count": len(frame),
        "column_count": len(frame.columns),
        "files": [{"path": "part-00000.parquet", "sha256": body_hash}],
    }
    manifest_temp = staging_root / "manifest.json.tmp"
    manifest_path = staging_root / "manifest.json"
    manifest_temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(manifest_temp, manifest_path)
    published_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_root, published_root)
    return {
        **manifest,
        "manifest_path": str(published_root / "manifest.json"),
        "body_sha256": body_hash,
    }


def save_raw_upload(filename: str, payload: bytes) -> Path:
    raw_root = settings.root / "raw" / datetime.now(UTC).strftime("%Y-%m-%d")
    raw_root.mkdir(parents=True, exist_ok=True)
    safe_suffix = Path(filename).suffix.lower()
    destination = raw_root / f"{uuid.uuid4().hex}{safe_suffix}"
    destination.write_bytes(payload)
    return destination


_verified_files: set[str] = set()


def manifest_files(manifest_path: str) -> list[Path]:
    """Resolve a manifest's files, verifying each one's sha256 against the manifest the first
    time it is read this process. Published files never change after the atomic publish rename
    (each version gets its own directory), so a file that verified once needs no re-hashing —
    this keeps the check from adding a full-file hash to every single query.
    """
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    files = []
    for item in manifest["files"]:
        file_path = path.parent / item["path"]
        if not file_path.is_file():
            raise FileNotFoundError("게시된 데이터 파일 일부를 찾을 수 없습니다.")
        key = str(file_path)
        if key not in _verified_files:
            if sha256_file(file_path) != item["sha256"]:
                raise ValueError(f"게시된 데이터 파일의 무결성 검증에 실패했습니다: {item['path']}")
            _verified_files.add(key)
        files.append(file_path)
    return files


def cleanup_staging() -> None:
    staging = settings.root / "staging"
    if not staging.exists():
        return
    for child in staging.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)

