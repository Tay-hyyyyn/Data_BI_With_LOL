"""Typed query plan. The only way callers describe a query; there is intentionally no raw-SQL entry point."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

FilterOperator = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_null"]
AggregateFunction = Literal["sum", "mean", "count", "min", "max", "quantile"]


@dataclass(frozen=True)
class Filter:
    column: str
    operator: FilterOperator
    value: Any = None


@dataclass(frozen=True)
class Aggregate:
    """`column=None` is only valid for `count` (COUNT(*)). `quantile` needs `q` in [0, 1] (linear interpolation)."""

    func: AggregateFunction
    column: str | None
    alias: str
    q: float | None = None


@dataclass(frozen=True)
class Bucket:
    """Equal-width bucket index of a numeric column: floor((x - low) / width), with `high` folded into the last bucket."""

    column: str
    low: float
    high: float
    bins: int
    alias: str


@dataclass(frozen=True)
class Sample:
    limit: int
    seed: int


@dataclass(frozen=True)
class QueryPlan:
    """With aggregates, `dimensions` and `buckets` are the GROUP BY keys. Without, `dimensions` is a plain projection."""

    dimensions: tuple[str, ...] = ()
    buckets: tuple[Bucket, ...] = ()
    aggregates: tuple[Aggregate, ...] = ()
    filters: tuple[Filter, ...] = ()
    order_by: tuple[tuple[str, bool], ...] = ()  # (dimension or alias, ascending)
    limit: int | None = None
    sample: Sample | None = None
