from __future__ import annotations

from types import SimpleNamespace

from app import database
from app.services import observability


def test_audit_events_and_failed_job_alerts_are_queryable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    observability.record_audit("user-1", "analyst", "POST", "/api/v1/datasets/upload", 201)
    with database.db() as connection:
        connection.execute("INSERT INTO jobs(id,job_type,status,progress,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", ("job-1", "source_sync", "failed", 100, "network unavailable", "now", "now"))

    assert observability.list_audit_events()[0]["actor_role"] == "analyst"
    assert observability.list_alerts()[0]["kind"] == "job_failed"
