from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..database import db
from ..query import materialize
from ..schemas import ColumnProfile, DatasetProfile, DatasetSummary, RecipeSummary
from ..storage import publish_dataframe, read_uploaded_file, save_raw_upload


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _semantic_type(series: pd.Series) -> str:
    name = str(series.name).lower()
    unique = int(series.nunique(dropna=True))
    count = max(int(series.notna().sum()), 1)
    if name == "id" or name.endswith("_id") or (unique / count > 0.98 and "id" in name):
        return "identifier"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_object_dtype(series) and any(token in name for token in ("date", "time", "timestamp", "일자", "날짜")):
        parsed = pd.to_datetime(series.dropna().head(1_000), errors="coerce")
        if not parsed.empty and parsed.notna().mean() >= 0.9:
            return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    avg_length = series.dropna().astype(str).str.len().mean() if count else 0
    if unique <= min(50, max(10, int(count * 0.2))) and avg_length < 80:
        return "categorical"
    return "text"


def _json_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def profile_frame(dataset_id: str, version_id: str, frame: pd.DataFrame) -> DatasetProfile:
    columns: list[ColumnProfile] = []
    row_count = len(frame)
    for name in frame.columns:
        series = frame[name]
        semantic = _semantic_type(series)
        non_null = series.dropna()
        profile = ColumnProfile(
            name=str(name),
            dtype=str(series.dtype),
            semantic_type=semantic,
            null_count=int(series.isna().sum()),
            null_ratio=round(float(series.isna().mean()) if row_count else 0.0, 6),
            unique_count=int(series.nunique(dropna=True)),
            sample_values=[_json_value(value) for value in non_null.head(3).tolist()],
        )
        if semantic == "numeric" and not non_null.empty:
            profile.minimum = float(non_null.min())
            profile.maximum = float(non_null.max())
            profile.mean = float(non_null.mean())
        elif semantic == "datetime" and not non_null.empty:
            profile.minimum = str(non_null.min())
            profile.maximum = str(non_null.max())
        columns.append(profile)
    return DatasetProfile(
        dataset_id=dataset_id,
        version_id=version_id,
        row_count=row_count,
        column_count=len(frame.columns),
        columns=columns,
    )


def ingest_upload(filename: str, payload: bytes, name: str | None = None, sheet_name: str | None = None) -> DatasetSummary:
    raw_path = save_raw_upload(filename, payload)
    frame = read_uploaded_file(raw_path, Path(filename).suffix, sheet_name)
    for column in frame.columns:
        if _semantic_type(frame[column]) == "datetime" and not pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    if len(frame) > 1_000_000 or len(frame.columns) > 200:
        raise ValueError("초기 제한은 100만 행, 200개 컬럼입니다.")
    return create_dataset_from_frame(frame, name or Path(filename).stem, "upload")


def create_dataset_from_frame(frame: pd.DataFrame, name: str, source_type: str) -> DatasetSummary:
    dataset_id = uuid.uuid4().hex
    version_id = uuid.uuid4().hex
    profile = profile_frame(dataset_id, version_id, frame)
    manifest = publish_dataframe(dataset_id, version_id, frame)
    now = utcnow()
    with db() as connection:
        connection.execute(
            "INSERT INTO datasets(id,name,source_type,created_at,current_version_id) VALUES(?,?,?,?,?)",
            (dataset_id, name, source_type, now, version_id),
        )
        connection.execute(
            """INSERT INTO dataset_versions
            (id,dataset_id,version_number,status,row_count,column_count,schema_json,manifest_path,body_sha256,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                version_id, dataset_id, 1, "published", len(frame), len(frame.columns),
                profile.model_dump_json(), manifest["manifest_path"], manifest["body_sha256"], now,
            ),
        )
    return DatasetSummary(
        id=dataset_id, name=name, source_type=source_type,
        created_at=now, current_version_id=version_id,
        row_count=len(frame), column_count=len(frame.columns), version_number=1,
    )


def list_datasets() -> list[DatasetSummary]:
    with db() as connection:
        rows = connection.execute(
            """SELECT d.*, v.row_count, v.column_count, v.version_number FROM datasets d
            LEFT JOIN dataset_versions v ON v.id=d.current_version_id ORDER BY d.created_at DESC"""
        ).fetchall()
    return [DatasetSummary(**dict(row)) for row in rows]


def get_dataset_by_name(name: str, source_type: str) -> DatasetSummary | None:
    with db() as connection:
        row = connection.execute(
            """SELECT d.*, v.row_count, v.column_count, v.version_number FROM datasets d
            LEFT JOIN dataset_versions v ON v.id=d.current_version_id
            WHERE d.name=? AND d.source_type=? ORDER BY d.created_at DESC LIMIT 1""",
            (name, source_type),
        ).fetchone()
    return DatasetSummary(**dict(row)) if row else None


def _frame_fingerprint(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256("\x1f".join(map(str, frame.columns)).encode("utf-8"))
    normalized = frame.astype(object).where(pd.notna(frame), "<NULL>").astype(str)
    digest.update(pd.util.hash_pandas_object(normalized, index=False).values.tobytes())
    return digest.hexdigest()


def sync_named_dataset(frame: pd.DataFrame, name: str, source_type: str) -> DatasetSummary:
    existing = get_dataset_by_name(name, source_type)
    if not existing:
        return create_dataset_from_frame(frame, name, source_type)
    current = read_frame(existing.id)
    if _frame_fingerprint(current) != _frame_fingerprint(frame):
        publish_new_version(existing.id, frame, "source synchronization", [])
    refreshed = get_dataset_by_name(name, source_type)
    if not refreshed:
        raise RuntimeError("동기화된 데이터셋을 다시 찾을 수 없습니다.")
    return refreshed


def get_version(dataset_id: str) -> dict:
    with db() as connection:
        row = connection.execute(
            """SELECT v.* FROM dataset_versions v JOIN datasets d ON d.current_version_id=v.id
            WHERE d.id=?""", (dataset_id,)
        ).fetchone()
    if not row:
        raise KeyError(dataset_id)
    return dict(row)


def get_profile(dataset_id: str) -> DatasetProfile:
    version = get_version(dataset_id)
    return DatasetProfile.model_validate_json(version["schema_json"])


def read_frame(dataset_id: str, limit: int | None = None) -> pd.DataFrame:
    return materialize(dataset_id, limit=limit)


def preview(dataset_id: str, limit: int = 100) -> dict:
    frame = read_frame(dataset_id, min(limit, 1_000))
    clean = frame.astype(object).where(pd.notna(frame), None)
    for column in clean.columns:
        clean[column] = clean[column].map(_json_value)
    return {"columns": [str(c) for c in clean.columns], "rows": clean.to_dict(orient="records")}


_MAX_VERSION_ATTEMPTS = 10


def publish_new_version(dataset_id: str, frame: pd.DataFrame, recipe_name: str, steps: list[dict]) -> dict:
    """Publish `frame` as the dataset's next version, retrying the version-number allocation on
    a UNIQUE collision from a concurrent writer.

    Reading `MAX(version_number)` and inserting it used to happen in two separate connections, so
    two concurrent transforms on the same dataset could both compute the same "next" number and
    one would fail with an uncaught `IntegrityError`, leaving its already-published Parquet
    orphaned. Allocating and inserting now happen in one transaction, and a collision (which is
    still possible: SQLite does not take a write lock for the `SELECT`, so two transactions can
    both read the same MAX before either writes) is retried with a freshly read MAX rather than
    surfaced as a 500.
    """
    version_id = uuid.uuid4().hex
    recipe_id = uuid.uuid4().hex
    profile = profile_frame(dataset_id, version_id, frame)
    manifest = publish_dataframe(dataset_id, version_id, frame)
    now = utcnow()
    for attempt in range(_MAX_VERSION_ATTEMPTS):
        try:
            with db() as connection:
                exists = connection.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)).fetchone()
                if not exists:
                    raise KeyError(dataset_id)
                next_version = connection.execute(
                    "SELECT COALESCE(MAX(version_number),0)+1 AS next_version FROM dataset_versions WHERE dataset_id=?",
                    (dataset_id,),
                ).fetchone()["next_version"]
                version_number = int(next_version)
                connection.execute(
                    """INSERT INTO dataset_versions
                    (id,dataset_id,version_number,status,row_count,column_count,schema_json,manifest_path,body_sha256,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (version_id, dataset_id, version_number, "published", len(frame), len(frame.columns),
                     profile.model_dump_json(), manifest["manifest_path"], manifest["body_sha256"], now),
                )
                connection.execute("UPDATE datasets SET current_version_id=? WHERE id=?", (version_id, dataset_id))
                connection.execute(
                    "INSERT INTO recipes(id,dataset_id,name,steps_json,created_at) VALUES(?,?,?,?,?)",
                    (recipe_id, dataset_id, recipe_name, json.dumps(steps, ensure_ascii=False), now),
                )
            break
        except sqlite3.IntegrityError:
            if attempt == _MAX_VERSION_ATTEMPTS - 1:
                raise
    return {
        "dataset_id": dataset_id, "version_id": version_id, "version_number": version_number,
        "row_count": len(frame), "column_count": len(frame.columns), "recipe_id": recipe_id,
    }


def list_recipes(dataset_id: str) -> list[RecipeSummary]:
    """Version-publish lineage for a dataset: every transform recipe and sync that produced a
    new version, newest first. Written by `publish_new_version` but never read before this."""
    with db() as connection:
        exists = connection.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if not exists:
            raise KeyError(dataset_id)
        rows = connection.execute(
            "SELECT * FROM recipes WHERE dataset_id=? ORDER BY created_at DESC", (dataset_id,)
        ).fetchall()
    return [
        RecipeSummary(id=row["id"], dataset_id=row["dataset_id"], name=row["name"], steps=json.loads(row["steps_json"]), created_at=row["created_at"])
        for row in rows
    ]
