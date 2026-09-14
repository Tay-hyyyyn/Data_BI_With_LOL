from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ..database import db
from ..schemas import ColumnProfile, DatasetProfile, DatasetSummary
from ..storage import manifest_files, publish_dataframe, read_uploaded_file, save_raw_upload


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
        row_count=len(frame), column_count=len(frame.columns),
    )


def list_datasets() -> list[DatasetSummary]:
    with db() as connection:
        rows = connection.execute(
            """SELECT d.*, v.row_count, v.column_count FROM datasets d
            LEFT JOIN dataset_versions v ON v.id=d.current_version_id ORDER BY d.created_at DESC"""
        ).fetchall()
    return [DatasetSummary(**dict(row)) for row in rows]


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
    version = get_version(dataset_id)
    files = [str(path).replace("'", "''") for path in manifest_files(version["manifest_path"])]
    quoted = ",".join(f"'{path}'" for path in files)
    query = f"SELECT * FROM read_parquet([{quoted}])"
    if limit is not None:
        query += " LIMIT ?"
    with duckdb.connect(":memory:") as connection:
        return connection.execute(query, [limit] if limit is not None else []).fetchdf()


def preview(dataset_id: str, limit: int = 100) -> dict:
    frame = read_frame(dataset_id, min(limit, 1_000))
    clean = frame.astype(object).where(pd.notna(frame), None)
    for column in clean.columns:
        clean[column] = clean[column].map(_json_value)
    return {"columns": [str(c) for c in clean.columns], "rows": clean.to_dict(orient="records")}


def publish_new_version(dataset_id: str, frame: pd.DataFrame, recipe_name: str, steps: list[dict]) -> dict:
    version_id = uuid.uuid4().hex
    recipe_id = uuid.uuid4().hex
    with db() as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(version_number),0)+1 AS next_version FROM dataset_versions WHERE dataset_id=?",
            (dataset_id,),
        ).fetchone()
    if not row:
        raise KeyError(dataset_id)
    version_number = int(row["next_version"])
    profile = profile_frame(dataset_id, version_id, frame)
    manifest = publish_dataframe(dataset_id, version_id, frame)
    now = utcnow()
    with db() as connection:
        exists = connection.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if not exists:
            raise KeyError(dataset_id)
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
    return {
        "dataset_id": dataset_id, "version_id": version_id, "version_number": version_number,
        "row_count": len(frame), "column_count": len(frame.columns), "recipe_id": recipe_id,
    }
