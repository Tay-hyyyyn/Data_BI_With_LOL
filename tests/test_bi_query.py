from __future__ import annotations

import pandas as pd
import pytest

from app.schemas import DatasetChartRequest, DatasetQuery, QueryFilter
from app.services import bi


def test_structured_query_groups_and_filters_without_sql(monkeypatch) -> None:
    frame = pd.DataFrame(
        {
            "channel": ["search", "search", "social"],
            "region": ["KR", "US", "KR"],
            "spend": [100.0, 50.0, 30.0],
        }
    )
    monkeypatch.setattr(bi, "get_version", lambda _: {"id": "version-1"})
    monkeypatch.setattr(bi, "read_frame", lambda _: frame)

    result = bi.query_dataset(
        "dataset-1",
        DatasetQuery(
            dimension="channel",
            measure="spend",
            aggregation="sum",
            filters=[QueryFilter(column="region", value="KR")],
        ),
    )

    assert result.version_id == "version-1"
    assert result.rows == [{"category": "search", "value": 100.0}, {"category": "social", "value": 30.0}]


def test_structured_query_rejects_unknown_columns(monkeypatch) -> None:
    monkeypatch.setattr(bi, "get_version", lambda _: {"id": "version-1"})
    monkeypatch.setattr(bi, "read_frame", lambda _: pd.DataFrame({"spend": [10]}))

    with pytest.raises(ValueError, match="존재하지 않는 컬럼"):
        bi.query_dataset("dataset-1", DatasetQuery(measure="revenue"))


def test_distinct_values_uses_complete_published_frame(monkeypatch) -> None:
    frame = pd.DataFrame({"channel": ["search", "social", "search", None]})
    monkeypatch.setattr(bi, "get_version", lambda _: {"id": "version-1"})
    monkeypatch.setattr(bi, "read_frame", lambda _: frame)

    result = bi.distinct_values("dataset-1", "channel")

    assert result.version_id == "version-1"
    assert result.values == [{"value": "search", "count": 2}, {"value": "social", "count": 1}, {"value": "(결측)", "count": 1}]


def test_chart_builder_returns_deterministic_scatter_sample(monkeypatch) -> None:
    frame = pd.DataFrame({"x": range(500), "y": range(500)})
    monkeypatch.setattr(bi, "get_version", lambda _: {"id": "version-1"})
    monkeypatch.setattr(bi, "read_frame", lambda _: frame)

    request = DatasetChartRequest(chart_type="scatter", x="x", y="y", sample_limit=100, seed=7)
    first = bi.build_chart("dataset-1", request)
    second = bi.build_chart("dataset-1", request)

    assert first.sample_size == 100
    assert first.chart_spec["series"][0]["data"] == second.chart_spec["series"][0]["data"]


def test_structured_query_keeps_numeric_time_dimension_in_ascending_order(monkeypatch) -> None:
    frame = pd.DataFrame({"minute": [20, 10, 15], "gold": [7000.0, 3000.0, 5000.0]})
    monkeypatch.setattr(bi, "get_version", lambda _: {"id": "version-1"})
    monkeypatch.setattr(bi, "read_frame", lambda _: frame)

    result = bi.query_dataset("dataset-1", DatasetQuery(dimension="minute", measure="gold", aggregation="mean"))

    assert [row["category"] for row in result.rows] == [10, 15, 20]


def test_structured_query_returns_multiple_series_on_one_time_axis(monkeypatch) -> None:
    frame = pd.DataFrame({"minute": [15, 10, 10, 15], "patch": ["16.18", "16.17", "16.18", "16.17"], "gold": [5100.0, 3000.0, 3200.0, 5000.0]})
    monkeypatch.setattr(bi, "get_version", lambda _: {"id": "version-1"})
    monkeypatch.setattr(bi, "read_frame", lambda _: frame)

    result = bi.query_dataset("dataset-1", DatasetQuery(dimension="minute", series="patch", measure="gold", aggregation="mean"))

    assert result.rows == [
        {"category": 10, "series": "16.17", "value": 3000.0},
        {"category": 10, "series": "16.18", "value": 3200.0},
        {"category": 15, "series": "16.17", "value": 5000.0},
        {"category": 15, "series": "16.18", "value": 5100.0},
    ]
