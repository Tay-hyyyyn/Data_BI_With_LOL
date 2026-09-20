from __future__ import annotations

import uuid

from ..database import db
from .datasets import utcnow


def record_audit(actor_id: str | None, actor_role: str | None, action: str, resource_path: str, outcome: int) -> None:
    with db() as connection:
        connection.execute(
            "INSERT INTO audit_events(id,actor_id,actor_role,action,resource_path,outcome,created_at) VALUES(?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, actor_id, actor_role, action, resource_path, outcome, utcnow()),
        )


def list_audit_events(limit: int = 50) -> list[dict]:
    with db() as connection:
        rows = connection.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (min(max(limit, 1), 200),)).fetchall()
    return [dict(row) for row in rows]


def list_alerts(limit: int = 50) -> list[dict]:
    with db() as connection:
        job_rows = connection.execute("SELECT id,job_type,error,updated_at FROM jobs WHERE status='failed' ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        source_rows = connection.execute("""SELECT event.id,event.source_id,event.status,event.message,event.created_at,source.name
            FROM source_sync_events event JOIN data_sources source ON source.id=event.source_id
            WHERE event.status IN ('failed','schema_changed') ORDER BY event.created_at DESC LIMIT ?""", (limit,)).fetchall()
    alerts = [{"kind": "job_failed", "id": row["id"], "title": row["job_type"], "message": row["error"], "created_at": row["updated_at"]} for row in job_rows]
    alerts.extend({"kind": row["status"], "id": row["id"], "title": row["name"], "message": row["message"], "created_at": row["created_at"]} for row in source_rows)
    return sorted(alerts, key=lambda item: item["created_at"], reverse=True)[:limit]
