"""Structured queries and chart specs. All computation is pushed down to DuckDB through `app.query`."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from ...query import Aggregate, Bucket, Filter, QueryPlan, Sample, is_orderable, run, scalar, schema_of
from ...schemas import DatasetChartRequest, DatasetChartResult, DatasetQuery, DatasetQueryResult, QueryFilter
from ..datasets import get_version

_TOP_GROUPS = 30


def _check_columns(schema: dict[str, str], columns: list[str | None]) -> None:
    missing = sorted({column for column in columns if column and column not in schema})
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")


def _filters(items: list[QueryFilter]) -> tuple[Filter, ...]:
    return tuple(Filter(item.column, item.operator, item.value) for item in items)


def query_dataset(dataset_id: str, request: DatasetQuery) -> DatasetQueryResult:
    version = get_version(dataset_id)
    schema = schema_of(dataset_id)
    _check_columns(schema, [request.dimension, request.series, request.measure, *(item.column for item in request.filters)])
    if request.aggregation != "count" and not request.measure:
        raise ValueError("선택한 집계에는 measure가 필요합니다.")

    aggregate = Aggregate(request.aggregation, request.measure, "value")
    filters = _filters(request.filters)
    rows: list[dict[str, Any]]
    if request.dimension:
        dimensions = (request.dimension, *([request.series] if request.series else []))
        ordered = is_orderable(schema[request.dimension])
        order_by: tuple[tuple[str, bool], ...]
        if ordered:
            order_by = ((request.dimension, True),)
            if request.series:
                order_by += ((request.series, True),)
        else:
            order_by = (("value", False), (request.dimension, True))
        plan = QueryPlan(
            dimensions=dimensions, aggregates=(aggregate,), filters=filters, order_by=order_by, limit=request.limit
        )
        frame = run(dataset_id, plan)
        frame = frame.rename(columns={request.dimension: "category", **({request.series: "series"} if request.series else {})})
        rows = json.loads(frame.to_json(orient="records", date_format="iso"))
    else:
        value = scalar(dataset_id, QueryPlan(aggregates=(aggregate,), filters=filters))
        rows = [{"value": value}]
    return DatasetQueryResult(
        dataset_id=dataset_id,
        version_id=version["id"],
        dimension=request.dimension,
        measure=request.measure,
        aggregation=request.aggregation,
        rows=rows,
    )


def _histogram(dataset_id: str, request: DatasetChartRequest, filters: tuple[Filter, ...]) -> tuple[dict, int]:
    present = (*filters, Filter(request.x, "not_null"))
    stats = run(
        dataset_id,
        QueryPlan(
            aggregates=(
                Aggregate("min", request.x, "lo"),
                Aggregate("max", request.x, "hi"),
                Aggregate("count", request.x, "n"),
            ),
            filters=present,
        ),
    ).iloc[0]
    total = int(stats["n"])
    if total:
        low, high = float(stats["lo"]), float(stats["hi"])
        if low == high:  # numpy.histogram widens a degenerate range by 0.5 on each side
            low, high = low - 0.5, high + 0.5
    else:
        low, high = 0.0, 1.0
    counts = np.zeros(request.bins, dtype=int)
    if total:
        buckets = run(
            dataset_id,
            QueryPlan(
                buckets=(Bucket(request.x, low, high, request.bins, "bin"),),
                aggregates=(Aggregate("count", None, "n"),),
                filters=present,
            ),
        )
        for index, count in zip(buckets["bin"], buckets["n"], strict=True):
            counts[int(index)] = int(count)
    edges = np.linspace(low, high, request.bins + 1)
    labels = [f"{edges[index]:.3g}–{edges[index + 1]:.3g}" for index in range(len(counts))]
    spec = {"xAxis": {"type": "category", "data": labels}, "yAxis": {"type": "value"}, "series": [{"type": "bar", "data": counts.tolist()}]}
    return spec, total


def _scatter(dataset_id: str, request: DatasetChartRequest, filters: tuple[Filter, ...]) -> tuple[dict, int]:
    if not request.y:
        raise ValueError("산점도에는 y 컬럼이 필요합니다.")
    sample = run(
        dataset_id,
        QueryPlan(
            dimensions=(request.x, request.y),
            filters=(*filters, Filter(request.x, "not_null"), Filter(request.y, "not_null")),
            sample=Sample(request.sample_limit, request.seed),
        ),
    )
    points = sample.astype(float).values.tolist()
    spec = {"xAxis": {"type": "value", "name": request.x}, "yAxis": {"type": "value", "name": request.y}, "series": [{"type": "scatter", "data": points, "symbolSize": 7}]}
    return spec, len(sample)


def _boxplot(dataset_id: str, request: DatasetChartRequest, filters: tuple[Filter, ...]) -> tuple[dict, int]:
    if not request.group:
        raise ValueError("박스플롯에는 group 컬럼이 필요합니다.")
    quantiles = [Aggregate("quantile", request.x, f"q{index}", q=q) for index, q in enumerate((0, 0.25, 0.5, 0.75, 1))]
    frame = run(
        dataset_id,
        QueryPlan(
            dimensions=(request.group,),
            aggregates=(Aggregate("count", None, "n"), *quantiles),
            filters=(*filters, Filter(request.group, "not_null"), Filter(request.x, "not_null")),
            order_by=(("n", False), (request.group, True)),
            limit=_TOP_GROUPS,
        ),
    )
    labels = [str(category) for category in frame[request.group]]
    boxes = frame[[f"q{index}" for index in range(5)]].astype(float).values.tolist()
    spec = {"xAxis": {"type": "category", "data": labels}, "yAxis": {"type": "value", "name": request.x}, "series": [{"type": "boxplot", "data": boxes}]}
    return spec, int(frame["n"].sum())


def _heatmap(dataset_id: str, request: DatasetChartRequest, filters: tuple[Filter, ...]) -> tuple[dict, int]:
    if not request.y:
        raise ValueError("히트맵에는 두 번째 범주형 컬럼이 필요합니다.")
    present = (*filters, Filter(request.x, "not_null"), Filter(request.y, "not_null"))

    def top(column: str) -> list[Any]:
        ranked = run(
            dataset_id,
            QueryPlan(
                dimensions=(column,),
                aggregates=(Aggregate("count", None, "n"),),
                filters=present,
                order_by=(("n", False), (column, True)),
                limit=_TOP_GROUPS,
            ),
        )
        return ranked[column].tolist()

    top_x, top_y = top(request.x), top(request.y)
    total = int(scalar(dataset_id, QueryPlan(aggregates=(Aggregate("count", None, "n"),), filters=present)) or 0)
    cells = run(
        dataset_id,
        QueryPlan(
            dimensions=(request.x, request.y),
            aggregates=(Aggregate("count", None, "n"),),
            filters=(*present, Filter(request.x, "in", top_x), Filter(request.y, "in", top_y)),
        ),
    )
    counts = {(row[request.x], row[request.y]): int(row["n"]) for row in cells.to_dict("records")}
    heat = [[x, y, counts.get((top_x[x], top_y[y]), 0)] for y in range(len(top_y)) for x in range(len(top_x))]
    maximum = max((point[2] for point in heat), default=0)
    spec = {
        "xAxis": {"type": "category", "data": [str(value) for value in top_x]},
        "yAxis": {"type": "category", "data": [str(value) for value in top_y]},
        "visualMap": {"min": 0, "max": maximum, "calculable": True},
        "series": [{"type": "heatmap", "data": heat}],
    }
    return spec, total


_CHARTS = {"histogram": _histogram, "scatter": _scatter, "boxplot": _boxplot, "heatmap": _heatmap}


def build_chart(dataset_id: str, request: DatasetChartRequest) -> DatasetChartResult:
    version = get_version(dataset_id)
    schema = schema_of(dataset_id)
    _check_columns(schema, [request.x, request.y, request.group, *(item.column for item in request.filters)])
    spec, sample_size = _CHARTS[request.chart_type](dataset_id, request, _filters(request.filters))
    spec["grid"] = {"left": 55, "right": 30, "top": 25, "bottom": 55, "containLabel": True}
    spec["tooltip"] = {"trigger": "item"}
    return DatasetChartResult(dataset_id=dataset_id, version_id=version["id"], chart_type=request.chart_type, sample_size=sample_size, chart_spec=spec)

