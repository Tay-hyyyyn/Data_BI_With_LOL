from __future__ import annotations

import json
import queue
import sqlite3
import threading
import uuid
from collections.abc import Callable
from typing import Any

from ..database import db
from ..schemas import JobSummary
from .datasets import utcnow

INTERRUPTED = "서버가 재시작되어 작업이 중단되었습니다."


class LocalJobRunner:
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, Callable[[], dict[str, Any]]] | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        # The queue lives in memory, so any row still queued/running belongs to a process that no longer exists.
        recover_stale_jobs()
        self._thread = threading.Thread(target=self._work, name="data-bi-local-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        self._queue.put(None)
        self._thread.join(timeout=3)

    def create_job(self, connection: sqlite3.Connection, job_type: str) -> str:
        """Insert a queued job row inside the caller's transaction. Pair with `enqueue` after it commits."""
        job_id, now = uuid.uuid4().hex, utcnow()
        connection.execute(
            "INSERT INTO jobs(id,job_type,status,progress,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (job_id, job_type, "queued", 0, now, now),
        )
        return job_id

    def enqueue(self, job_id: str, task: Callable[[], dict[str, Any]]) -> None:
        self._queue.put((job_id, task))

    def submit(self, job_type: str, task: Callable[[], dict[str, Any]]) -> JobSummary:
        with db() as connection:
            job_id = self.create_job(connection, job_type)
        self.enqueue(job_id, task)
        return get_job(job_id)

    def _work(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            job_id, task = item
            self._update(job_id, "running", 10)
            try:
                result = task()
                self._update(job_id, "completed", 100, result=result)
            except Exception as error:  # 작업 경계에서 오류를 격리한다.
                self._update(job_id, "failed", 100, error=str(error))

    @staticmethod
    def _update(job_id: str, status: str, progress: int, result: dict | None = None, error: str | None = None) -> None:
        with db() as connection:
            connection.execute(
                "UPDATE jobs SET status=?,progress=?,result_json=?,error=?,updated_at=? WHERE id=?",
                (status, progress, json.dumps(result, ensure_ascii=False) if result is not None else None, error, utcnow(), job_id),
            )


def recover_stale_jobs() -> int:
    """Fail jobs left queued/running by a previous process. Returns how many were recovered."""
    with db() as connection:
        return connection.execute(
            "UPDATE jobs SET status='failed',progress=100,error=?,updated_at=? WHERE status IN ('queued','running')",
            (INTERRUPTED, utcnow()),
        ).rowcount


def _summary(row: sqlite3.Row) -> JobSummary:
    return JobSummary(
        id=row["id"], job_type=row["job_type"], status=row["status"], progress=row["progress"],
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error=row["error"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


def get_job(job_id: str) -> JobSummary:
    with db() as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    return _summary(row)


def list_jobs(limit: int = 50) -> list[JobSummary]:
    with db() as connection:
        rows = connection.execute("SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [_summary(row) for row in rows]


job_runner = LocalJobRunner()
