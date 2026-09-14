from __future__ import annotations

import json
import uuid

from ..database import db
from ..schemas import PipelineSummary, PipelineWrite
from .datasets import utcnow


def _from_row(row) -> PipelineSummary:
    return PipelineSummary(
        id=row["id"], name=row["name"], dataset_id=row["dataset_id"],
        pipeline_type=row["pipeline_type"], config=json.loads(row["config_json"]),
        enabled=bool(row["enabled"]), created_at=row["created_at"], updated_at=row["updated_at"],
    )


def create_pipeline(payload: PipelineWrite) -> PipelineSummary:
    pipeline_id, now = uuid.uuid4().hex, utcnow()
    with db() as connection:
        if not connection.execute("SELECT 1 FROM datasets WHERE id=?", (payload.dataset_id,)).fetchone():
            raise KeyError(payload.dataset_id)
        connection.execute(
            "INSERT INTO pipelines(id,name,dataset_id,pipeline_type,config_json,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (pipeline_id, payload.name, payload.dataset_id, payload.pipeline_type, json.dumps(payload.config, ensure_ascii=False), int(payload.enabled), now, now),
        )
    return get_pipeline(pipeline_id)


def get_pipeline(pipeline_id: str) -> PipelineSummary:
    with db() as connection:
        row = connection.execute("SELECT * FROM pipelines WHERE id=?", (pipeline_id,)).fetchone()
    if not row:
        raise KeyError(pipeline_id)
    return _from_row(row)


def list_pipelines(enabled: bool | None = None) -> list[PipelineSummary]:
    with db() as connection:
        if enabled is None:
            rows = connection.execute("SELECT * FROM pipelines ORDER BY updated_at DESC").fetchall()
        else:
            rows = connection.execute("SELECT * FROM pipelines WHERE enabled=? ORDER BY updated_at DESC", (int(enabled),)).fetchall()
    return [_from_row(row) for row in rows]


def set_pipeline_enabled(pipeline_id: str, enabled: bool) -> PipelineSummary:
    with db() as connection:
        updated = connection.execute("UPDATE pipelines SET enabled=?,updated_at=? WHERE id=?", (int(enabled), utcnow(), pipeline_id)).rowcount
    if not updated:
        raise KeyError(pipeline_id)
    return get_pipeline(pipeline_id)


def existing_run_job(pipeline_id: str, idempotency_key: str) -> str | None:
    with db() as connection:
        row = connection.execute("SELECT job_id FROM pipeline_runs WHERE pipeline_id=? AND idempotency_key=?", (pipeline_id, idempotency_key)).fetchone()
    return row["job_id"] if row else None


def record_run(pipeline_id: str, idempotency_key: str, job_id: str) -> None:
    with db() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO pipeline_runs(pipeline_id,idempotency_key,job_id,created_at) VALUES(?,?,?,?)",
            (pipeline_id, idempotency_key, job_id, utcnow()),
        )
