from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "ColumnProfile",
    "DatasetProfile",
    "DatasetSummary",
    "Preview",
    "TransformRequest",
    "TransformResult",
    "TransformStep",
]


class DatasetSummary(BaseModel):
    id: str
    name: str
    source_type: str
    created_at: str
    current_version_id: str | None
    row_count: int | None = None
    column_count: int | None = None
    version_number: int | None = None


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


class Preview(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]


class TransformStep(BaseModel):
    operation: Literal[
        "select",
        "rename",
        "cast",
        "fill_missing",
        "drop_missing",
        "drop_duplicates",
        "filter",
        "calculate",
        "aggregate",
        "pivot",
        "join",
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
