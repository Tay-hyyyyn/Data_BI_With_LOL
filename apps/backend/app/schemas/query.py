from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .common import QueryFilter

__all__ = ["DatasetChartRequest", "DatasetChartResult", "DatasetQuery", "DatasetQueryResult", "MetricSummary", "MetricWrite"]


class DatasetQuery(BaseModel):
    dimension: str | None = None
    series: str | None = None
    measure: str | None = None
    aggregation: Literal["sum", "mean", "count", "min", "max"] = "sum"
    filters: list[QueryFilter] = Field(default_factory=list, max_length=20)
    limit: int = Field(100, ge=1, le=1_000)


class DatasetQueryResult(BaseModel):
    dataset_id: str
    version_id: str
    dimension: str | None
    measure: str | None
    aggregation: str
    rows: list[dict[str, Any]]


class DatasetChartRequest(BaseModel):
    chart_type: Literal["histogram", "scatter", "boxplot", "heatmap"]
    x: str
    y: str | None = None
    group: str | None = None
    filters: list[QueryFilter] = Field(default_factory=list, max_length=20)
    sample_limit: int = Field(2_000, ge=100, le=20_000)
    bins: int = Field(20, ge=5, le=100)
    seed: int = 42


class DatasetChartResult(BaseModel):
    dataset_id: str
    version_id: str
    chart_type: str
    sample_size: int
    chart_spec: dict[str, Any]


class MetricWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dataset_id: str
    aggregation: Literal["sum", "mean", "count", "min", "max", "ratio"]
    column: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    unit: str | None = Field(None, max_length=30)
    description: str | None = Field(None, max_length=500)


class MetricSummary(BaseModel):
    id: str
    name: str
    dataset_id: str
    unit: str | None
    description: str | None
    value: float
