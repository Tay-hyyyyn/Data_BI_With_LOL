from __future__ import annotations

from fastapi import APIRouter

from ..errors import api_errors, unprocessable
from ..schemas import MetricSummary, MetricWrite
from ..services.bi import create_metric, list_metrics

router = APIRouter()


@router.post("/metrics", response_model=MetricSummary, status_code=201)
def define_metric(metric: MetricWrite) -> MetricSummary:
    with api_errors(unprocessable(KeyError, ValueError)):
        return create_metric(metric)


@router.get("/metrics", response_model=list[MetricSummary])
def metrics(dataset_id: str | None = None) -> list[MetricSummary]:
    with api_errors(unprocessable(KeyError, ValueError)):
        return list_metrics(dataset_id)
