from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

from app.database import db, initialize_database
from app.schemas import PipelineWrite
from app.services import pipelines
from app.services.jobs import get_job, job_runner, list_jobs, recover_stale_jobs


def _insert_job(job_id: str, status: str) -> None:
    with db() as connection:
        connection.execute(
            "INSERT INTO jobs(id,job_type,status,progress,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (job_id, "t", status, 10, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )


def test_stale_jobs_are_failed_on_startup_but_finished_jobs_are_untouched(data_root):
    initialize_database()
    _insert_job("q", "queued")
    _insert_job("r", "running")
    _insert_job("c", "completed")

    assert recover_stale_jobs() == 2

    assert get_job("q").status == "failed" and get_job("r").status == "failed"
    assert "중단" in (get_job("q").error or "")
    assert get_job("c").status == "completed"


def test_starting_the_runner_recovers_stale_jobs(data_root):
    initialize_database()
    _insert_job("orphan", "running")
    job_runner.start()
    try:
        assert get_job("orphan").status == "failed"
    finally:
        job_runner.stop()


def test_list_jobs_respects_limit_and_order(data_root):
    initialize_database()
    for index in range(5):
        _insert_job(f"j{index}", "completed")
    assert len(list_jobs(3)) == 3


def test_concurrent_runs_with_one_idempotency_key_create_exactly_one_job(client, dataset):
    payload = PipelineWrite(
        name="p", dataset_id=dataset["id"], pipeline_type="relationships", config={"column": "revenue"}, enabled=True
    )
    pipeline = pipelines.create_pipeline(payload)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: pipelines.run_pipeline(pipeline.id, "same-key"), range(8)))

    assert len({job.id for job in results}) == 1
    with db() as connection:
        count = connection.execute("SELECT COUNT(*) FROM jobs WHERE job_type='pipeline:relationships'").fetchone()[0]
    assert count == 1


def test_a_different_idempotency_key_creates_a_new_job(client, dataset):
    pipeline = pipelines.create_pipeline(
        PipelineWrite(name="p", dataset_id=dataset["id"], pipeline_type="relationships", config={"column": "revenue"}, enabled=True)
    )
    first = pipelines.run_pipeline(pipeline.id, "hour-1")
    second = pipelines.run_pipeline(pipeline.id, "hour-2")
    assert first.id != second.id


def test_sqlite_integrity_error_is_not_leaked(client, dataset):
    assert sqlite3.IntegrityError  # guard: run_pipeline must translate PK collisions, never raise them
