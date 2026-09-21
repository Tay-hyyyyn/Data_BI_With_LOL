from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = ["RelationshipItem", "RelationshipRequest", "RelationshipResponse"]


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
