from __future__ import annotations

from fastapi import APIRouter

from ..errors import api_errors, not_found
from ..schemas import DashboardSummary, DashboardWrite
from ..services.bi import (
    clone_dashboard,
    get_dashboard,
    list_dashboards,
    save_dashboard,
    set_dashboard_published,
    update_dashboard,
)

router = APIRouter()

_NOT_FOUND = not_found("대시보드를 찾을 수 없습니다.")


@router.get("/dashboards", response_model=list[DashboardSummary])
def dashboards() -> list[DashboardSummary]:
    return list_dashboards()


@router.get("/dashboards/{dashboard_id}", response_model=DashboardSummary)
def dashboard(dashboard_id: str) -> DashboardSummary:
    with api_errors(_NOT_FOUND):
        return get_dashboard(dashboard_id)


@router.post("/dashboards", response_model=DashboardSummary, status_code=201)
def create_dashboard(payload: DashboardWrite) -> DashboardSummary:
    return save_dashboard(payload)


@router.put("/dashboards/{dashboard_id}", response_model=DashboardSummary)
def edit_dashboard(dashboard_id: str, payload: DashboardWrite) -> DashboardSummary:
    with api_errors(_NOT_FOUND):
        return update_dashboard(dashboard_id, payload)


@router.post("/dashboards/{dashboard_id}/clone", response_model=DashboardSummary, status_code=201)
def duplicate_dashboard(dashboard_id: str) -> DashboardSummary:
    with api_errors(_NOT_FOUND):
        return clone_dashboard(dashboard_id)


@router.post("/dashboards/{dashboard_id}/publish", response_model=DashboardSummary)
def publish_dashboard(dashboard_id: str, published: bool = True) -> DashboardSummary:
    with api_errors(_NOT_FOUND, (PermissionError, 403, None)):
        return set_dashboard_published(dashboard_id, published)
