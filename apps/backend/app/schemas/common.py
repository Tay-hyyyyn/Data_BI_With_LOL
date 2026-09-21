from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

__all__ = ["JobSummary", "QueryFilter"]


class QueryFilter(BaseModel):
    column: str
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in"] = "eq"
    value: Any


class JobSummary(BaseModel):
    id: str
    job_type: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    updated_at: str
