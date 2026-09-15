from __future__ import annotations

import json
import uuid

import numpy as np
import pandas as pd

from ..database import db
from ..config import settings
from ..schemas import DashboardSummary, DashboardWrite, DatasetChartRequest, DatasetChartResult, DatasetQuery, DatasetQueryResult, MetricSummary, MetricWrite
from .datasets import get_version, read_frame, utcnow


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
    required = [column for column in (request.dimension, request.measure) if column]
    required.extend(item.column for item in request.filters)
    missing = sorted({column for column in required if column not in frame.columns})
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")

    filtered = _apply_filters(frame, request.filters)

    if request.aggregation != "count" and not request.measure:
        raise ValueError("선택한 집계에는 measure가 필요합니다.")
    if request.dimension:
        grouped = filtered.groupby(request.dimension, dropna=False)
        if request.aggregation == "count":
            values = grouped.size() if not request.measure else grouped[request.measure].count()
        else:
            values = getattr(grouped[request.measure], request.aggregation)()
        result = values.rename("value").reset_index().rename(columns={request.dimension: "category"})
        result = result.sort_values("value", ascending=False).head(request.limit)
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


def create_metric(metric: MetricWrite) -> MetricSummary:
    frame = read_frame(metric.dataset_id)
    required = [column for column in (metric.column, metric.numerator, metric.denominator) if column]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")
    if metric.aggregation == "ratio":
        if not metric.numerator or not metric.denominator:
            raise ValueError("비율 지표에는 numerator와 denominator가 필요합니다.")
        denominator = float(frame[metric.denominator].sum())
        value = float(frame[metric.numerator].sum()) / denominator if denominator else np.nan
    elif metric.aggregation == "count":
        value = float(frame[metric.column].count() if metric.column else len(frame))
    else:
        if not metric.column:
            raise ValueError("이 집계에는 column이 필요합니다.")
        value = float(getattr(frame[metric.column], metric.aggregation)())
    metric_id, now = uuid.uuid4().hex, utcnow()
    definition = metric.model_dump(exclude={"name", "dataset_id", "unit", "description"})
    with db() as connection:
        connection.execute(
            """INSERT INTO metrics(id,dataset_id,name,definition_json,unit,description,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (metric_id, metric.dataset_id, metric.name, json.dumps(definition), metric.unit, metric.description, now),
        )
    return MetricSummary(id=metric_id, name=metric.name, dataset_id=metric.dataset_id, unit=metric.unit, description=metric.description, value=value)


def save_dashboard(payload: DashboardWrite) -> DashboardSummary:
    dashboard_id, now = uuid.uuid4().hex, utcnow()
    definition = {"widgets": payload.widgets, "filters": payload.filters}
    with db() as connection:
        connection.execute(
            "INSERT INTO dashboards(id,name,definition_json,visibility,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (dashboard_id, payload.name, json.dumps(definition, ensure_ascii=False), "private", now, now),
        )
    return DashboardSummary(id=dashboard_id, name=payload.name, **definition, visibility="private", created_at=now, updated_at=now)


def list_dashboards() -> list[DashboardSummary]:
    with db() as connection:
        rows = connection.execute("SELECT * FROM dashboards ORDER BY updated_at DESC").fetchall()
    result = []
    for row in rows:
        definition = json.loads(row["definition_json"])
        result.append(DashboardSummary(id=row["id"], name=row["name"], **definition, visibility=row["visibility"], created_at=row["created_at"], updated_at=row["updated_at"]))
    return result


def get_dashboard(dashboard_id: str) -> DashboardSummary:
    dashboard = next((item for item in list_dashboards() if item.id == dashboard_id), None)
    if not dashboard:
        raise KeyError(dashboard_id)
    return dashboard


def update_dashboard(dashboard_id: str, payload: DashboardWrite) -> DashboardSummary:
    now = utcnow()
    definition = {"widgets": payload.widgets, "filters": payload.filters}
    with db() as connection:
        updated = connection.execute(
            "UPDATE dashboards SET name=?, definition_json=?, updated_at=? WHERE id=?",
            (payload.name, json.dumps(definition, ensure_ascii=False), now, dashboard_id),
        ).rowcount
    if not updated:
        raise KeyError(dashboard_id)
    return get_dashboard(dashboard_id)


def clone_dashboard(dashboard_id: str) -> DashboardSummary:
    dashboard = get_dashboard(dashboard_id)
    return save_dashboard(DashboardWrite(name=f"{dashboard.name} 복사본", widgets=dashboard.widgets, filters=dashboard.filters))


def set_dashboard_published(dashboard_id: str, published: bool) -> DashboardSummary:
    if published:
        dashboard = get_dashboard(dashboard_id)
        dataset_ids = {widget.get("dataset_id") for widget in dashboard.widgets if widget.get("dataset_id")}
        if dataset_ids:
            placeholders = ",".join("?" for _ in dataset_ids)
            with db() as connection:
                sources = connection.execute(
                    f"SELECT name, source_type FROM datasets WHERE id IN ({placeholders})", tuple(dataset_ids)
                ).fetchall()
            contains_restricted_lol = any(
                row["source_type"].startswith(("riot-", "lolps-"))
                or row["name"].lower().startswith(("lol ", "lol.ps"))
                for row in sources
            )
            if contains_restricted_lol and not settings.riot_enable_public_data:
                raise PermissionError("LoL 원천·벤치마크 데이터 대시보드는 RIOT_ENABLE_PUBLIC_DATA=true 승인 전 게시할 수 없습니다.")
    now = utcnow()
    with db() as connection:
        updated = connection.execute(
            "UPDATE dashboards SET visibility=?, updated_at=? WHERE id=?",
            ("published" if published else "private", now, dashboard_id),
        ).rowcount
    if not updated:
        raise KeyError(dashboard_id)
    return next(item for item in list_dashboards() if item.id == dashboard_id)
