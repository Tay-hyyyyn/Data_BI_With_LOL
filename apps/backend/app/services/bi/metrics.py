from __future__ import annotations

import json
import uuid

import pandas as pd

from ...database import db
from ...query import Aggregate, QueryPlan, run, scalar, schema_of
from ...schemas import MetricSummary, MetricWrite
from ..datasets import utcnow


def _metric_value(dataset_id: str, metric: MetricWrite, schema: dict[str, str]) -> float:
    """Evaluate one stored metric definition against the current published version (pushed down to DuckDB)."""
    required = [column for column in (metric.column, metric.numerator, metric.denominator) if column]
    missing = [column for column in required if column not in schema]
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")
    if metric.aggregation == "ratio":
        if not metric.numerator or not metric.denominator:
            raise ValueError("비율 지표에는 numerator와 denominator가 필요합니다.")
        totals = run(
            dataset_id,
            QueryPlan(aggregates=(Aggregate("sum", metric.numerator, "numerator"), Aggregate("sum", metric.denominator, "denominator"))),
        ).iloc[0]
        numerator = 0.0 if pd.isna(totals["numerator"]) else float(totals["numerator"])
        denominator = 0.0 if pd.isna(totals["denominator"]) else float(totals["denominator"])
        return numerator / denominator if denominator else float("nan")
    if metric.aggregation == "count":
        return scalar(dataset_id, QueryPlan(aggregates=(Aggregate("count", metric.column, "value"),))) or 0.0
    if not metric.column:
        raise ValueError("이 집계에는 column이 필요합니다.")
    value = scalar(dataset_id, QueryPlan(aggregates=(Aggregate(metric.aggregation, metric.column, "value"),)))
    if value is None:  # an empty sum is 0; an empty mean/min/max is undefined
        return 0.0 if metric.aggregation == "sum" else float("nan")
    return value


def create_metric(metric: MetricWrite) -> MetricSummary:
    value = _metric_value(metric.dataset_id, metric, schema_of(metric.dataset_id))
    now = utcnow()
    definition = metric.model_dump(exclude={"name", "dataset_id", "unit", "description"})
    with db() as connection:
        existing = connection.execute("SELECT id FROM metrics WHERE dataset_id=? AND name=?", (metric.dataset_id, metric.name)).fetchone()
        if existing:
            metric_id = existing["id"]
            connection.execute("UPDATE metrics SET definition_json=?,unit=?,description=? WHERE id=?", (json.dumps(definition), metric.unit, metric.description, metric_id))
        else:
            metric_id = uuid.uuid4().hex
            connection.execute(
                """INSERT INTO metrics(id,dataset_id,name,definition_json,unit,description,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (metric_id, metric.dataset_id, metric.name, json.dumps(definition), metric.unit, metric.description, now),
            )
    return MetricSummary(id=metric_id, name=metric.name, dataset_id=metric.dataset_id, unit=metric.unit, description=metric.description, value=value)


def list_metrics(dataset_id: str | None = None) -> list[MetricSummary]:
    with db() as connection:
        if dataset_id:
            rows = connection.execute("SELECT * FROM metrics WHERE dataset_id=? ORDER BY created_at DESC", (dataset_id,)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM metrics ORDER BY created_at DESC").fetchall()
    result = []
    schemas: dict[str, dict[str, str]] = {}
    for row in rows:
        definition = json.loads(row["definition_json"])
        metric = MetricWrite(name=row["name"], dataset_id=row["dataset_id"], unit=row["unit"], description=row["description"], **definition)
        if metric.dataset_id not in schemas:
            schemas[metric.dataset_id] = schema_of(metric.dataset_id)
        result.append(MetricSummary(id=row["id"], name=metric.name, dataset_id=metric.dataset_id, unit=metric.unit, description=metric.description, value=_metric_value(metric.dataset_id, metric, schemas[metric.dataset_id])))
    return result
