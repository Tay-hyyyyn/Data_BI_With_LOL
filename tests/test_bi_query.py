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


def test_chart_builder_returns_deterministic_scatter_sample(monkeypatch) -> None:
    frame = pd.DataFrame({"x": range(500), "y": range(500)})
    monkeypatch.setattr(bi, "get_version", lambda _: {"id": "version-1"})
    monkeypatch.setattr(bi, "read_frame", lambda _: frame)

    request = DatasetChartRequest(chart_type="scatter", x="x", y="y", sample_limit=100, seed=7)
    first = bi.build_chart("dataset-1", request)
    second = bi.build_chart("dataset-1", request)

    assert first.sample_size == 100
    assert first.chart_spec["series"][0]["data"] == second.chart_spec["series"][0]["data"]
