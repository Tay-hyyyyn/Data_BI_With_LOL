from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    id: str
    name: str
    source_type: str
    created_at: str
    current_version_id: str | None
    row_count: int | None = None
    column_count: int | None = None


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    semantic_type: Literal["numeric", "categorical", "datetime", "text", "identifier"]
    null_count: int
    null_ratio: float
    unique_count: int
    sample_values: list[Any] = Field(default_factory=list)
    minimum: float | str | None = None
    maximum: float | str | None = None
    mean: float | None = None


class DatasetProfile(BaseModel):
    dataset_id: str
    version_id: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]


class RelationshipRequest(BaseModel):
    column: str
    candidate_limit: int = Field(30, ge=1, le=200)
    sample_limit: int = Field(20_000, ge=100, le=100_000)
    result_limit: int = Field(5, ge=1, le=20)
    minimum_pair_samples: int = Field(100, ge=20, le=10_000)
    seed: int = 42
    entity_key: str | None = None
    time_column: str | None = None
    analysis_grain: Literal["mean", "latest"] | None = None


class RelationshipItem(BaseModel):
    column: str
    relation_type: str
    method: str
    score: float
    direction: Literal["positive", "negative", "none"]
    sample_size: int
    null_ratio: float
    reason: str
    chart_spec: dict[str, Any]


class RelationshipResponse(BaseModel):
    dataset_id: str
    version_id: str
    selected_column: str
    compared_candidates: int
    sampled: bool
    items: list[RelationshipItem]


class TransformStep(BaseModel):
    operation: Literal[
        "select", "rename", "cast", "fill_missing", "drop_missing",
        "drop_duplicates", "filter", "calculate", "aggregate", "pivot",
    ]
    config: dict[str, Any] = Field(default_factory=dict)


class TransformRequest(BaseModel):
    name: str = Field("새 전처리 버전", min_length=1, max_length=100)
    steps: list[TransformStep] = Field(min_length=1, max_length=50)


class TransformResult(BaseModel):
    dataset_id: str
    version_id: str
    version_number: int
    row_count: int
    column_count: int
    recipe_id: str


class LolStaticSyncRequest(BaseModel):
    version: str | None = None
    bootstrap_samples: int = Field(200, ge=20, le=2_000)


class LolStarterDashboardRequest(BaseModel):
    patch: str = Field(min_length=1, max_length=20)


class RiotAccountResolveRequest(BaseModel):
    game_name: str = Field(min_length=1, max_length=64)
    tag_line: str = Field(min_length=1, max_length=16)


class RiotAccountSummary(BaseModel):
    puuid: str
    game_name: str
    tag_line: str


class RiotMatchCollectRequest(BaseModel):
    puuid: str = Field(min_length=20, max_length=128)
    count: int = Field(10, ge=1, le=100)


class RiotMatchProcessRequest(BaseModel):
    match_ids: list[str] = Field(min_length=1, max_length=1_000)
    snapshot_minutes: list[int] = Field(default=[10, 15, 20], min_length=1, max_length=12)
    item_dataset_id: str | None = None


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


class QueryFilter(BaseModel):
    column: str
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in"] = "eq"
    value: Any


class DatasetQuery(BaseModel):
    dimension: str | None = None
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


class DashboardWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    widgets: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    filters: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class DashboardSummary(BaseModel):
    id: str
    name: str
    widgets: list[dict[str, Any]]
    filters: list[dict[str, Any]]
    visibility: Literal["private", "published"]
    created_at: str
    updated_at: str


class JobSummary(BaseModel):
    id: str
    job_type: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class PipelineWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dataset_id: str
    pipeline_type: Literal["relationships", "transform"]
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = False


class PipelineSummary(PipelineWrite):
    id: str
    created_at: str
    updated_at: str


class PipelineRunRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
