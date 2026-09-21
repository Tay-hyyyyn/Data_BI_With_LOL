from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = ["DashboardSummary", "DashboardWrite"]


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
