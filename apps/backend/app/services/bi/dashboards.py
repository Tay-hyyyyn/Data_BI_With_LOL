from __future__ import annotations

import json
import uuid

from ...config import settings
from ...database import db
from ...schemas import DashboardSummary, DashboardWrite
from ..datasets import utcnow


def save_dashboard(payload: DashboardWrite) -> DashboardSummary:
    dashboard_id, now = uuid.uuid4().hex, utcnow()
    definition = {"widgets": payload.widgets, "filters": payload.filters}
    with db() as connection:
        connection.execute(
            "INSERT INTO dashboards(id,name,definition_json,visibility,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (dashboard_id, payload.name, json.dumps(definition, ensure_ascii=False), "private", now, now),
        )
    return DashboardSummary(id=dashboard_id, name=payload.name, **definition, visibility="private", created_at=now, updated_at=now)


def save_or_update_dashboard(name: str, widgets: list[dict], filters: list[dict] | None = None) -> DashboardSummary:
    """Upsert a system-generated, private dashboard without duplicating it."""
    payload = DashboardWrite(name=name, widgets=widgets, filters=filters or [])
    with db() as connection:
        row = connection.execute(
            "SELECT id FROM dashboards WHERE name=? ORDER BY updated_at DESC LIMIT 1", (name,)
        ).fetchone()
    return update_dashboard(row["id"], payload) if row else save_dashboard(payload)


def list_dashboards() -> list[DashboardSummary]:
    with db() as connection:
        rows = connection.execute("SELECT * FROM dashboards ORDER BY updated_at DESC").fetchall()
    result = []
    for row in rows:
        definition = json.loads(row["definition_json"])
        result.append(DashboardSummary(id=row["id"], name=row["name"], **definition, visibility=row["visibility"], created_at=row["created_at"], updated_at=row["updated_at"]))
    return result


def get_dashboard(dashboard_id: str) -> DashboardSummary:
    dashboard = next((item for item in list_dashboards() if item.id == dashboard_id), None)
    if not dashboard:
        raise KeyError(dashboard_id)
    return dashboard


def update_dashboard(dashboard_id: str, payload: DashboardWrite) -> DashboardSummary:
    now = utcnow()
    definition = {"widgets": payload.widgets, "filters": payload.filters}
    with db() as connection:
        updated = connection.execute(
            "UPDATE dashboards SET name=?, definition_json=?, updated_at=? WHERE id=?",
            (payload.name, json.dumps(definition, ensure_ascii=False), now, dashboard_id),
        ).rowcount
    if not updated:
        raise KeyError(dashboard_id)
    return get_dashboard(dashboard_id)


def clone_dashboard(dashboard_id: str) -> DashboardSummary:
    dashboard = get_dashboard(dashboard_id)
    return save_dashboard(DashboardWrite(name=f"{dashboard.name} 복사본", widgets=dashboard.widgets, filters=dashboard.filters))


def set_dashboard_published(dashboard_id: str, published: bool) -> DashboardSummary:
    if published:
        dashboard = get_dashboard(dashboard_id)
        dataset_ids = {widget.get("dataset_id") for widget in dashboard.widgets if widget.get("dataset_id")}
        if dataset_ids:
            placeholders = ",".join("?" for _ in dataset_ids)
            with db() as connection:
                sources = connection.execute(
                    f"SELECT name, source_type FROM datasets WHERE id IN ({placeholders})", tuple(dataset_ids)  # noqa: S608 - placeholders are generated "?" only
                ).fetchall()
            contains_restricted_lol = any(
                row["source_type"].startswith(("riot-", "lolps-"))
                or row["name"].lower().startswith(("lol ", "lol.ps"))
                for row in sources
            )
            if contains_restricted_lol and not settings.riot_enable_public_data:
                raise PermissionError("LoL 원천·벤치마크 데이터 대시보드는 RIOT_ENABLE_PUBLIC_DATA=true 승인 전 게시할 수 없습니다.")
    now = utcnow()
    with db() as connection:
        updated = connection.execute(
            "UPDATE dashboards SET visibility=?, updated_at=? WHERE id=?",
            ("published" if published else "private", now, dashboard_id),
        ).rowcount
    if not updated:
        raise KeyError(dashboard_id)
    return next(item for item in list_dashboards() if item.id == dashboard_id)
