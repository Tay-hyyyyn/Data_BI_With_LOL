from __future__ import annotations

import json
import sqlite3
import uuid

from ..database import db
from ..errors import ConflictError
from ..schemas import JobSummary, PipelineSummary, PipelineWrite, RelationshipRequest, TransformRequest
from .datasets import utcnow
from .jobs import get_job, job_runner
from .relationships import analyze_cached
from .transforms import run_recipe


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


def run_pipeline(pipeline_id: str, idempotency_key: str) -> JobSummary:
    """Queue one pipeline run, returning the existing job when the idempotency key was already used."""
    pipeline = get_pipeline(pipeline_id)
    if not pipeline.enabled:
        raise ConflictError("비활성 파이프라인은 실행할 수 없습니다.")
    previous = existing_run_job(pipeline_id, idempotency_key)
    if previous:
        return get_job(previous)
    if pipeline.pipeline_type == "relationships":
        relation_request = RelationshipRequest.model_validate(pipeline.config)

        def task() -> dict:
            return analyze_cached(pipeline.dataset_id, relation_request).model_dump(mode="json")
    else:
        transform_request = TransformRequest.model_validate(pipeline.config)

        def task() -> dict:
            return run_recipe(pipeline.dataset_id, transform_request).model_dump(mode="json")
    # The job row and its idempotency record are written in one transaction, *before* anything is queued.
    # Concurrent callers with the same key collide on the primary key and get the winner's job back,
    # so a key can never start two runs.
    try:
        with db() as connection:
            job_id = job_runner.create_job(connection, f"pipeline:{pipeline.pipeline_type}")
            connection.execute(
                "INSERT INTO pipeline_runs(pipeline_id,idempotency_key,job_id,created_at) VALUES(?,?,?,?)",
                (pipeline_id, idempotency_key, job_id, utcnow()),
            )
    except sqlite3.IntegrityError:
        winner = existing_run_job(pipeline_id, idempotency_key)
        if winner is None:
            raise
        return get_job(winner)
    job_runner.enqueue(job_id, task)
    return get_job(job_id)
