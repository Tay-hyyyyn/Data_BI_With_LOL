from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ...schemas import DatasetChartRequest, DatasetChartResult, DatasetQuery, DatasetQueryResult
from ..datasets import get_version, read_frame


def _apply_filters(frame, filters):
    filtered = frame
    for item in filters:
        series = filtered[item.column]
        if item.operator == "eq":
            mask = series.astype(str).eq(str(item.value))
        elif item.operator == "ne":
            mask = ~series.astype(str).eq(str(item.value))
        elif item.operator == "in":
            values = item.value if isinstance(item.value, list) else [item.value]
            mask = series.astype(str).isin([str(value) for value in values])
        else:
            numeric = np.asarray(series, dtype=float)
            target = float(item.value)
            mask = {"gt": numeric > target, "gte": numeric >= target, "lt": numeric < target, "lte": numeric <= target}[item.operator]
        filtered = filtered.loc[mask]
    return filtered


def query_dataset(dataset_id: str, request: DatasetQuery) -> DatasetQueryResult:
    version = get_version(dataset_id)
    frame = read_frame(dataset_id)
    required = [column for column in (request.dimension, request.series, request.measure) if column]
    required.extend(item.column for item in request.filters)
    missing = sorted({column for column in required if column not in frame.columns})
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")

    filtered = _apply_filters(frame, request.filters)

    if request.aggregation != "count" and not request.measure:
        raise ValueError("선택한 집계에는 measure가 필요합니다.")
    if request.dimension:
        group_columns = [request.dimension] + ([request.series] if request.series else [])
        grouped = filtered.groupby(group_columns, dropna=False)
        if request.aggregation == "count":
            values = grouped.size() if not request.measure else grouped[request.measure].count()
        else:
            values = getattr(grouped[request.measure], request.aggregation)()
        result = values.rename("value").reset_index().rename(columns={request.dimension: "category", request.series: "series"})
        is_ordered_dimension = pd.api.types.is_numeric_dtype(filtered[request.dimension]) or pd.api.types.is_datetime64_any_dtype(filtered[request.dimension])
        sort_columns = ["category", "series"] if request.series and is_ordered_dimension else (["value"] if not is_ordered_dimension else ["category"])
        result = result.sort_values(sort_columns, ascending=is_ordered_dimension).head(request.limit)
        rows = json.loads(result.to_json(orient="records", date_format="iso"))
    else:
        if request.aggregation == "count":
            value = len(filtered) if not request.measure else filtered[request.measure].count()
        else:
            value = getattr(filtered[request.measure], request.aggregation)()
        rows = [{"value": None if np.isnan(value) else float(value)}]
    return DatasetQueryResult(
        dataset_id=dataset_id,
        version_id=version["id"],
        dimension=request.dimension,
        measure=request.measure,
        aggregation=request.aggregation,
        rows=rows,
    )


def build_chart(dataset_id: str, request: DatasetChartRequest) -> DatasetChartResult:
    version = get_version(dataset_id)
    frame = read_frame(dataset_id)
    required = [column for column in (request.x, request.y, request.group) if column]
    required.extend(item.column for item in request.filters)
    missing = sorted({column for column in required if column not in frame.columns})
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")
    filtered = _apply_filters(frame, request.filters)

    if request.chart_type == "histogram":
        values = np.asarray(filtered[request.x].dropna(), dtype=float)
        counts, edges = np.histogram(values, bins=request.bins)
        labels = [f"{edges[index]:.3g}–{edges[index + 1]:.3g}" for index in range(len(counts))]
        spec = {"xAxis": {"type": "category", "data": labels}, "yAxis": {"type": "value"}, "series": [{"type": "bar", "data": counts.tolist()}]}
        sample_size = len(values)
    elif request.chart_type == "scatter":
        if not request.y:
            raise ValueError("산점도에는 y 컬럼이 필요합니다.")
        sample = filtered[[request.x, request.y]].dropna()
        if len(sample) > request.sample_limit:
            sample = sample.sample(request.sample_limit, random_state=request.seed)
        points = sample.astype(float).values.tolist()
        spec = {"xAxis": {"type": "value", "name": request.x}, "yAxis": {"type": "value", "name": request.y}, "series": [{"type": "scatter", "data": points, "symbolSize": 7}]}
        sample_size = len(sample)
    elif request.chart_type == "boxplot":
        if not request.group:
            raise ValueError("박스플롯에는 group 컬럼이 필요합니다.")
        pairs = filtered[[request.group, request.x]].dropna()
        top = pairs[request.group].value_counts().head(30).index
        pairs = pairs.loc[pairs[request.group].isin(top)]
        labels, boxes = [], []
        for category, values in pairs.groupby(request.group, sort=False)[request.x]:
            numeric = np.asarray(values, dtype=float)
            labels.append(str(category))
            boxes.append(np.quantile(numeric, [0, 0.25, 0.5, 0.75, 1]).tolist())
        spec = {"xAxis": {"type": "category", "data": labels}, "yAxis": {"type": "value", "name": request.x}, "series": [{"type": "boxplot", "data": boxes}]}
        sample_size = len(pairs)
    else:
        if not request.y:
            raise ValueError("히트맵에는 두 번째 범주형 컬럼이 필요합니다.")
        pairs = filtered[[request.x, request.y]].dropna().astype(str)
        top_x = pairs[request.x].value_counts().head(30).index
        top_y = pairs[request.y].value_counts().head(30).index
        table = pd.crosstab(pairs[request.y], pairs[request.x]).reindex(index=top_y, columns=top_x, fill_value=0)
        heat = [[x, y, int(table.iloc[y, x])] for y in range(len(table.index)) for x in range(len(table.columns))]
        maximum = max((point[2] for point in heat), default=0)
        spec = {"xAxis": {"type": "category", "data": table.columns.tolist()}, "yAxis": {"type": "category", "data": table.index.tolist()}, "visualMap": {"min": 0, "max": maximum, "calculable": True}, "series": [{"type": "heatmap", "data": heat}]}
        sample_size = len(pairs)
    spec["grid"] = {"left": 55, "right": 30, "top": 25, "bottom": 55, "containLabel": True}
    spec["tooltip"] = {"trigger": "item"}
    return DatasetChartResult(dataset_id=dataset_id, version_id=version["id"], chart_type=request.chart_type, sample_size=sample_size, chart_spec=spec)
