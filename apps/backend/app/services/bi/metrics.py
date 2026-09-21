from __future__ import annotations

import json
import uuid

import numpy as np
import pandas as pd

from ...database import db
from ...schemas import MetricSummary, MetricWrite
from ..datasets import read_frame, utcnow


def _metric_value(frame: pd.DataFrame, metric: MetricWrite) -> float:
    """Evaluate one stored metric definition against the current published version."""
    required = [column for column in (metric.column, metric.numerator, metric.denominator) if column]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")
    if metric.aggregation == "ratio":
        if not metric.numerator or not metric.denominator:
            raise ValueError("비율 지표에는 numerator와 denominator가 필요합니다.")
        denominator = float(frame[metric.denominator].sum())
        return float(frame[metric.numerator].sum()) / denominator if denominator else np.nan
    if metric.aggregation == "count":
        return float(frame[metric.column].count() if metric.column else len(frame))
    if not metric.column:
        raise ValueError("이 집계에는 column이 필요합니다.")
    return float(getattr(frame[metric.column], metric.aggregation)())


def create_metric(metric: MetricWrite) -> MetricSummary:
    frame = read_frame(metric.dataset_id)
    value = _metric_value(frame, metric)
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
    for row in rows:
        definition = json.loads(row["definition_json"])
        metric = MetricWrite(name=row["name"], dataset_id=row["dataset_id"], unit=row["unit"], description=row["description"], **definition)
        result.append(MetricSummary(id=row["id"], name=metric.name, dataset_id=metric.dataset_id, unit=metric.unit, description=metric.description, value=_metric_value(read_frame(metric.dataset_id), metric)))
    return result
