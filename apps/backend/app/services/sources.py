from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from .. import database
from ..schemas import DataSourceSummary, DataSourceWrite, SourceSyncEvent
from .datasets import get_profile, sync_named_dataset, utcnow


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label}은 영문·숫자·밑줄만 사용한 DB 식별자여야 합니다.")
    return value


def _demo_path() -> Path:
    return database.settings.root / "sources" / "demo_analytics.sqlite"


def ensure_demo_database() -> Path:
    """Create a deterministic local operational DB used to exercise the DB pipeline."""
    path = _demo_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                ordered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                channel TEXT NOT NULL,
                region TEXT NOT NULL,
                customer_segment TEXT NOT NULL,
                spend REAL NOT NULL,
                revenue REAL NOT NULL,
                status TEXT NOT NULL
            )"""
        )
        existing = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if existing == 0:
            rng = np.random.default_rng(20260920)
            dates = pd.date_range("2026-01-01", periods=240, freq="h")
            channels = np.array(["Search", "Social", "Display", "Email"])
            regions = np.array(["KR-Seoul", "KR-Busan", "KR-Incheon"])
            segments = np.array(["new", "returning", "vip"])
            rows = []
            for index, date in enumerate(dates, start=1):
                spend = round(float(rng.uniform(30_000, 180_000)), 2)
                revenue = round(spend * float(rng.uniform(0.7, 3.4)), 2)
                rows.append((
                    index, date.isoformat(), (date + pd.Timedelta(5, unit="min")).isoformat(),
                    str(rng.choice(channels)), str(rng.choice(regions)), str(rng.choice(segments)),
                    spend, revenue, "completed" if rng.random() > 0.08 else "refunded",
                ))
            connection.executemany(
                "INSERT INTO orders(order_id,ordered_at,updated_at,channel,region,customer_segment,spend,revenue,status) VALUES(?,?,?,?,?,?,?,?,?)",
                rows,
            )
    return path


def _from_row(row) -> DataSourceSummary:
    data = dict(row)
    return DataSourceSummary(
        id=data["id"], name=data["name"], source_type=data["source_type"],
        table_name=data["table_name"], primary_key=data["primary_key"],
        watermark_column=data["watermark_column"], connection_env_var=data["connection_env_var"],
        enabled=bool(data["enabled"]), dataset_id=data.get("dataset_id"),
        last_watermark=data.get("last_watermark"), last_synced_at=data.get("last_synced_at"),
        last_row_count=int(data.get("last_row_count") or 0),
        created_at=data["created_at"], updated_at=data["updated_at"],
    )


def list_sources(enabled: bool | None = None) -> list[DataSourceSummary]:
    sql = """SELECT s.*, state.dataset_id, state.last_watermark, state.last_synced_at, state.last_row_count
        FROM data_sources s LEFT JOIN source_sync_state state ON state.source_id=s.id"""
    params: tuple = ()
    if enabled is not None:
        sql += " WHERE s.enabled=?"
        params = (int(enabled),)
    sql += " ORDER BY s.updated_at DESC"
    with database.db() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [_from_row(row) for row in rows]


def get_source(source_id: str) -> DataSourceSummary:
    with database.db() as connection:
        row = connection.execute(
            """SELECT s.*, state.dataset_id, state.last_watermark, state.last_synced_at, state.last_row_count
            FROM data_sources s LEFT JOIN source_sync_state state ON state.source_id=s.id WHERE s.id=?""",
            (source_id,),
        ).fetchone()
    if not row:
        raise KeyError(source_id)
    return _from_row(row)


def create_source(payload: DataSourceWrite) -> DataSourceSummary:
    _identifier(payload.table_name, "테이블명")
    _identifier(payload.primary_key, "기본 키")
    if payload.watermark_column:
        _identifier(payload.watermark_column, "증분 기준 컬럼")
    if payload.source_type == "postgresql" and not payload.connection_env_var:
        raise ValueError("PostgreSQL 소스는 연결 URL을 담은 환경변수 이름이 필요합니다.")
    if payload.source_type == "sqlite_demo":
        ensure_demo_database()
    source_id, now = uuid.uuid4().hex, utcnow()
    with database.db() as connection:
        try:
            connection.execute(
                """INSERT INTO data_sources(id,name,source_type,table_name,primary_key,watermark_column,connection_env_var,enabled,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (source_id, payload.name, payload.source_type, payload.table_name, payload.primary_key,
                 payload.watermark_column, payload.connection_env_var, int(payload.enabled), now, now),
            )
            connection.execute("INSERT INTO source_sync_state(source_id) VALUES(?)", (source_id,))
        except sqlite3.IntegrityError as error:
            raise ValueError("같은 이름의 데이터 소스가 이미 등록되어 있습니다.") from error
    return get_source(source_id)


def set_source_enabled(source_id: str, enabled: bool) -> DataSourceSummary:
    with database.db() as connection:
        if not connection.execute("UPDATE data_sources SET enabled=?,updated_at=? WHERE id=?", (int(enabled), utcnow(), source_id)).rowcount:
            raise KeyError(source_id)
    return get_source(source_id)


def _schema_hash(payload: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _source_schema(source: DataSourceSummary) -> list[dict[str, str]]:
    table = _identifier(source.table_name, "테이블명")
    if source.source_type == "sqlite_demo":
        with sqlite3.connect(ensure_demo_database()) as connection:
            rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if not rows:
            raise ValueError("원본 DB 테이블을 찾을 수 없습니다.")
        return [{"name": str(row[1]), "dtype": str(row[2]).upper()} for row in rows]
    url = os.getenv(source.connection_env_var or "")
    if not url:
        raise ValueError(f"환경변수 {source.connection_env_var}에 PostgreSQL 읽기 전용 URL을 설정하세요.")
    try:
        import psycopg
    except ImportError as error:
        raise ValueError("PostgreSQL 연결에는 `pip install -e '.[database]'`가 필요합니다.") from error
    with psycopg.connect(url) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        rows = connection.execute(
            """SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position""",
            (table,),
        ).fetchall()
    if not rows:
        raise ValueError("원본 DB 테이블을 찾을 수 없습니다.")
    return [{"name": str(row[0]), "dtype": str(row[1]).upper()} for row in rows]


def _record_event(source_id: str, mode: str, status: str, synced_rows: int = 0, row_count: int | None = None, message: str | None = None) -> None:
    with database.db() as connection:
        connection.execute(
            "INSERT INTO source_sync_events(id,source_id,mode,status,synced_rows,row_count,message,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, source_id, mode, status, synced_rows, row_count, message, utcnow()),
        )


def list_sync_events(source_id: str, limit: int = 20) -> list[SourceSyncEvent]:
    with database.db() as connection:
        rows = connection.execute(
            "SELECT * FROM source_sync_events WHERE source_id=? ORDER BY created_at DESC LIMIT ?",
            (source_id, min(max(limit, 1), 100)),
        ).fetchall()
    return [SourceSyncEvent(**dict(row)) for row in rows]


def source_status(source_id: str) -> dict:
    source = get_source(source_id)
    quality: dict[str, object] | None = None
    if source.dataset_id:
        profile = get_profile(source.dataset_id)
        quality = {
            "dataset_id": source.dataset_id,
            "row_count": profile.row_count,
            "column_count": profile.column_count,
            "null_ratio_mean": round(sum(item.null_ratio for item in profile.columns) / max(profile.column_count, 1), 6),
            "identifier_columns": [item.name for item in profile.columns if item.semantic_type == "identifier"],
        }
    with database.db() as connection:
        snapshots = connection.execute("SELECT row_count,column_count,null_ratio_mean,created_at FROM source_quality_snapshots WHERE source_id=? ORDER BY created_at DESC LIMIT 20", (source_id,)).fetchall()
    return {"source": source.model_dump(mode="json"), "quality": quality, "quality_history": [dict(item) for item in snapshots], "events": [item.model_dump(mode="json") for item in list_sync_events(source_id)]}


def _read_source(source: DataSourceSummary, last_watermark: str | None, mode: str) -> pd.DataFrame:
    table = _identifier(source.table_name, "테이블명")
    primary_key = _identifier(source.primary_key, "기본 키")
    watermark = _identifier(source.watermark_column, "증분 기준 컬럼") if source.watermark_column else None
    where, params = "", []
    if mode == "incremental" and last_watermark and watermark:
        where, params = f" WHERE {watermark} > ?", [last_watermark]
    query = f"SELECT * FROM {table}{where} ORDER BY {primary_key}"
    if source.source_type == "sqlite_demo":
        with sqlite3.connect(ensure_demo_database()) as connection:
            return pd.read_sql_query(query, connection, params=params)
    url = os.getenv(source.connection_env_var or "")
    if not url:
        raise ValueError(f"환경변수 {source.connection_env_var}에 PostgreSQL 읽기 전용 URL을 설정하세요.")
    try:
        import psycopg
    except ImportError as error:
        raise ValueError("PostgreSQL 연결에는 `pip install -e '.[database]'`가 필요합니다.") from error
    with psycopg.connect(url) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        return pd.read_sql_query(query, connection, params=params)


def sync_source(source_id: str, mode: str = "incremental", accept_schema_change: bool = False) -> dict:
    source = get_source(source_id)
    if not source.enabled:
        raise ValueError("비활성 데이터 소스는 동기화할 수 없습니다.")
    incoming = _read_source(source, source.last_watermark, mode)
    schema = _source_schema(source)
    schema_hash = _schema_hash(schema)
    with database.db() as connection:
        previous_schema = connection.execute("SELECT schema_hash FROM source_schema_snapshots WHERE source_id=?", (source.id,)).fetchone()
    if previous_schema and previous_schema["schema_hash"] != schema_hash and not accept_schema_change:
        message = "원본 DB 스키마가 변경되어 게시를 중단했습니다. 컬럼 변경을 검토한 뒤 명시적으로 수락하세요."
        _record_event(source.id, mode, "schema_changed", message=message)
        raise ValueError(message)
    with database.db() as connection:
        connection.execute(
            """INSERT INTO source_schema_snapshots(source_id,schema_hash,schema_json,captured_at) VALUES(?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET schema_hash=excluded.schema_hash,schema_json=excluded.schema_json,captured_at=excluded.captured_at""",
            (source.id, schema_hash, json.dumps(schema, ensure_ascii=False), utcnow()),
        )
    if incoming.empty:
        _record_event(source.id, mode, "unchanged")
        return {"source_id": source.id, "dataset_id": source.dataset_id, "synced_rows": 0, "status": "unchanged"}
    if source.dataset_id and mode == "incremental":
        from .datasets import read_frame
        current = read_frame(source.dataset_id)
        combined = pd.concat([current, incoming], ignore_index=True)
        frame = combined.drop_duplicates(subset=[source.primary_key], keep="last")
    else:
        frame = incoming.drop_duplicates(subset=[source.primary_key], keep="last")
    dataset = sync_named_dataset(frame, f"DB · {source.name} · {source.table_name}", "database")
    next_watermark = source.last_watermark
    if source.watermark_column:
        value = incoming[source.watermark_column].dropna().max()
        next_watermark = str(value) if pd.notna(value) else source.last_watermark
    now = utcnow()
    with database.db() as connection:
        connection.execute(
            """UPDATE source_sync_state SET dataset_id=?,last_watermark=?,last_synced_at=?,last_row_count=? WHERE source_id=?""",
            (dataset.id, next_watermark, now, len(frame), source.id),
        )
        profile = get_profile(dataset.id)
        connection.execute(
            "INSERT INTO source_quality_snapshots(id,source_id,dataset_id,row_count,column_count,null_ratio_mean,created_at) VALUES(?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, source.id, dataset.id, profile.row_count, profile.column_count, sum(item.null_ratio for item in profile.columns) / max(profile.column_count, 1), now),
        )
    _record_event(source.id, mode, "published", len(incoming), len(frame))
    return {"source_id": source.id, "dataset_id": dataset.id, "synced_rows": len(incoming), "row_count": len(frame), "status": "published"}


def sync_source_with_retry(source_id: str, mode: str = "incremental", accept_schema_change: bool = False, attempts: int = 2) -> dict:
    """Retry only transient transport/storage errors; schema and validation errors fail immediately."""
    for attempt in range(1, attempts + 1):
        try:
            return sync_source(source_id, mode, accept_schema_change)
        except (sqlite3.OperationalError, OSError) as error:
            if attempt == attempts:
                _record_event(source_id, mode, "failed", message=f"{attempt}회 시도 후 실패: {error}")
                raise
            time.sleep(0.1 * attempt)
        except Exception as error:
            if not isinstance(error, ValueError):
                _record_event(source_id, mode, "failed", message=str(error))
            raise
    raise RuntimeError("동기화 재시도 예산을 모두 사용했습니다.")
