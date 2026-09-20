from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import DashboardSummary, DashboardWrite, MetricSummary, MetricWrite
from ..services.bi import (
    clone_dashboard,
    create_metric,
    get_dashboard,
    list_dashboards,
    list_metrics,
    save_dashboard,
    set_dashboard_published,
    update_dashboard,
)


router = APIRouter(tags=["bi"])


@router.post("/api/v1/metrics", response_model=MetricSummary, status_code=201)
def define_metric(metric: MetricWrite) -> MetricSummary:
    try:
        return create_metric(metric)
    except (KeyError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


@router.get("/api/v1/metrics", response_model=list[MetricSummary])
def metrics(dataset_id: str | None = None) -> list[MetricSummary]:
    try:
        return list_metrics(dataset_id)
    except (KeyError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


@router.get("/api/v1/dashboards", response_model=list[DashboardSummary])
def dashboards() -> list[DashboardSummary]:
    return list_dashboards()


@router.get("/api/v1/dashboards/{dashboard_id}", response_model=DashboardSummary)
def dashboard(dashboard_id: str) -> DashboardSummary:
    try:
        return get_dashboard(dashboard_id)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error


@router.post("/api/v1/dashboards", response_model=DashboardSummary, status_code=201)
def create_dashboard(payload: DashboardWrite) -> DashboardSummary:
    return save_dashboard(payload)


@router.put("/api/v1/dashboards/{dashboard_id}", response_model=DashboardSummary)
def edit_dashboard(dashboard_id: str, payload: DashboardWrite) -> DashboardSummary:
    try:
        return update_dashboard(dashboard_id, payload)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error


@router.post("/api/v1/dashboards/{dashboard_id}/clone", response_model=DashboardSummary, status_code=201)
def duplicate_dashboard(dashboard_id: str) -> DashboardSummary:
    try:
        return clone_dashboard(dashboard_id)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error


@router.post("/api/v1/dashboards/{dashboard_id}/publish", response_model=DashboardSummary)
def publish_dashboard(dashboard_id: str, published: bool = True) -> DashboardSummary:
    try:
        return set_dashboard_published(dashboard_id, published)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
