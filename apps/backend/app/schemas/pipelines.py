from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = ["PipelineRunRequest", "PipelineSummary", "PipelineWrite"]


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
