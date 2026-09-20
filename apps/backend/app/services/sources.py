from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from .. import database
from ..schemas import DataSourceSummary, DataSourceWrite
from .datasets import sync_named_dataset, utcnow


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


def sync_source(source_id: str, mode: str = "incremental") -> dict:
    source = get_source(source_id)
    if not source.enabled:
        raise ValueError("비활성 데이터 소스는 동기화할 수 없습니다.")
    incoming = _read_source(source, source.last_watermark, mode)
    if incoming.empty:
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
    return {"source_id": source.id, "dataset_id": dataset.id, "synced_rows": len(incoming), "row_count": len(frame), "status": "published"}
