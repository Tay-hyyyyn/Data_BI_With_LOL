"""Typed query plan. The only way callers describe a query; there is intentionally no raw-SQL entry point."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

FilterOperator = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in"]
AggregateFunction = Literal["sum", "mean", "count", "min", "max"]


@dataclass(frozen=True)
class Filter:
    column: str
    operator: FilterOperator
    value: Any


@dataclass(frozen=True)
class Aggregate:
    func: AggregateFunction
    column: str | None
    alias: str


@dataclass(frozen=True)
class Sample:
    limit: int
    seed: int


@dataclass(frozen=True)
class QueryPlan:
    dimensions: tuple[str, ...] = ()
    aggregates: tuple[Aggregate, ...] = ()
    filters: tuple[Filter, ...] = ()
    order_by: tuple[tuple[str, bool], ...] = ()  # (column or alias, ascending)
    limit: int | None = None
    sample: Sample | None = None
