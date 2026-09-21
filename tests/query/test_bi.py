"""BI queries/charts/metrics run as pushed-down DuckDB SQL against really published datasets."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from app.schemas import DatasetChartRequest, DatasetQuery, MetricWrite, QueryFilter
from app.services import bi


def test_structured_query_groups_and_filters(publish) -> None:
    frame = pd.DataFrame({"channel": ["search", "search", "social"], "region": ["KR", "US", "KR"], "spend": [100.0, 50.0, 30.0]})
    dataset_id = publish(frame)

    result = bi.query_dataset(
        dataset_id,
        DatasetQuery(dimension="channel", measure="spend", aggregation="sum", filters=[QueryFilter(column="region", value="KR")]),
    )

    assert result.rows == [{"category": "search", "value": 100.0}, {"category": "social", "value": 30.0}]
    assert result.version_id


def test_unordered_dimension_ranks_by_value_descending(publish) -> None:
    dataset_id = publish(pd.DataFrame({"channel": ["a", "b", "b", "c"], "spend": [1.0, 5.0, 5.0, 3.0]}))
    result = bi.query_dataset(dataset_id, DatasetQuery(dimension="channel", measure="spend", aggregation="sum"))
    assert [row["category"] for row in result.rows] == ["b", "c", "a"]


def test_structured_query_rejects_unknown_columns(publish) -> None:
    dataset_id = publish(pd.DataFrame({"spend": [10]}))
    with pytest.raises(ValueError, match="존재하지 않는 컬럼"):
        bi.query_dataset(dataset_id, DatasetQuery(measure="revenue"))


def test_query_needs_a_measure_unless_counting(publish) -> None:
    dataset_id = publish(pd.DataFrame({"channel": ["a", "b", "b"]}))
    with pytest.raises(ValueError, match="measure"):
        bi.query_dataset(dataset_id, DatasetQuery(dimension="channel", aggregation="sum"))
    counted = bi.query_dataset(dataset_id, DatasetQuery(dimension="channel", aggregation="count"))
    assert {row["category"]: row["value"] for row in counted.rows} == {"a": 1, "b": 2}


def test_aggregate_without_dimension_returns_one_value(publish) -> None:
    dataset_id = publish(pd.DataFrame({"spend": [1.0, 2.0, None]}))
    assert bi.query_dataset(dataset_id, DatasetQuery(measure="spend", aggregation="sum")).rows == [{"value": 3.0}]
    assert bi.query_dataset(dataset_id, DatasetQuery(aggregation="count")).rows == [{"value": 3}]
    assert bi.query_dataset(dataset_id, DatasetQuery(measure="spend", aggregation="count")).rows == [{"value": 2}]


def test_null_dimension_values_form_their_own_group_last(publish) -> None:
    dataset_id = publish(pd.DataFrame({"minute": [10, None, 10], "gold": [1.0, 2.0, 3.0]}))
    rows = bi.query_dataset(dataset_id, DatasetQuery(dimension="minute", measure="gold", aggregation="sum")).rows
    assert rows[0] == {"category": 10.0, "value": 4.0}
    assert rows[1]["category"] is None and rows[1]["value"] == 2.0


def test_numeric_time_dimension_is_ascending(publish) -> None:
    dataset_id = publish(pd.DataFrame({"minute": [20, 10, 15], "gold": [7000.0, 3000.0, 5000.0]}))
    result = bi.query_dataset(dataset_id, DatasetQuery(dimension="minute", measure="gold", aggregation="mean"))
    assert [row["category"] for row in result.rows] == [10, 15, 20]


def test_multiple_series_share_one_time_axis(publish) -> None:
    frame = pd.DataFrame(
        {"minute": [15, 10, 10, 15], "patch": ["16.18", "16.17", "16.18", "16.17"], "gold": [5100.0, 3000.0, 3200.0, 5000.0]}
    )
    result = bi.query_dataset(publish(frame), DatasetQuery(dimension="minute", series="patch", measure="gold", aggregation="mean"))
    assert result.rows == [
        {"category": 10, "series": "16.17", "value": 3000.0},
        {"category": 10, "series": "16.18", "value": 3200.0},
        {"category": 15, "series": "16.17", "value": 5000.0},
        {"category": 15, "series": "16.18", "value": 5100.0},
    ]


def test_limit_is_applied_after_grouping(publish) -> None:
    dataset_id = publish(pd.DataFrame({"k": list(range(50)), "v": [1.0] * 50}))
    result = bi.query_dataset(dataset_id, DatasetQuery(dimension="k", measure="v", aggregation="sum", limit=5))
    assert [row["category"] for row in result.rows] == [0, 1, 2, 3, 4]


def test_integer_filter_matches_a_column_that_became_float_because_of_nulls(publish) -> None:
    """Regression (B5): filters compared str(value) with astype(str), so 1 never matched the float column's '1.0'."""
    dataset_id = publish(pd.DataFrame({"region_id": [1, 2, None, 1], "spend": [10.0, 20.0, 30.0, 40.0]}))
    result = bi.query_dataset(
        dataset_id,
        DatasetQuery(measure="spend", aggregation="sum", filters=[QueryFilter(column="region_id", operator="eq", value=1)]),
    )
    assert result.rows == [{"value": 50.0}]


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [("gt", 20, 70.0), ("gte", 20, 90.0), ("lt", 20, 10.0), ("lte", 20, 30.0), ("ne", 20, 80.0)],
)
def test_comparison_operators(publish, operator, value, expected) -> None:
    dataset_id = publish(pd.DataFrame({"k": [10, 20, 30, 40], "v": [10.0, 20.0, 30.0, 40.0]}))
    query = DatasetQuery(measure="v", aggregation="sum", filters=[QueryFilter(column="k", operator=operator, value=value)])
    assert bi.query_dataset(dataset_id, query).rows == [{"value": expected}]


def test_in_filter_and_empty_in_filter(publish) -> None:
    dataset_id = publish(pd.DataFrame({"k": ["a", "b", "c"], "v": [1.0, 2.0, 4.0]}))
    hit = DatasetQuery(measure="v", aggregation="sum", filters=[QueryFilter(column="k", operator="in", value=["a", "c"])])
    none = DatasetQuery(measure="v", aggregation="sum", filters=[QueryFilter(column="k", operator="in", value=[])])
    assert bi.query_dataset(dataset_id, hit).rows == [{"value": 5.0}]
    assert bi.query_dataset(dataset_id, none).rows == [{"value": None}]


def test_unconvertible_filter_value_is_a_clear_error_not_silent_zero_rows(publish) -> None:
    dataset_id = publish(pd.DataFrame({"k": [1, 2], "v": [1.0, 2.0]}))
    query = DatasetQuery(measure="v", aggregation="sum", filters=[QueryFilter(column="k", operator="eq", value="abc")])
    with pytest.raises(ValueError, match="쿼리를 실행할 수 없습니다"):
        bi.query_dataset(dataset_id, query)


def test_sum_of_a_text_column_is_a_value_error(publish) -> None:
    dataset_id = publish(pd.DataFrame({"name": ["a", "b"]}))
    with pytest.raises(ValueError):
        bi.query_dataset(dataset_id, DatasetQuery(measure="name", aggregation="sum"))


def test_hostile_values_and_column_names_cannot_inject_sql(publish) -> None:
    dataset_id = publish(pd.DataFrame({"k": ["a", "b"], "v": [1.0, 2.0]}))
    payload = "a' OR '1'='1"
    result = bi.query_dataset(
        dataset_id, DatasetQuery(measure="v", aggregation="sum", filters=[QueryFilter(column="k", operator="eq", value=payload)])
    )
    assert result.rows == [{"value": None}]  # matched nothing; was not interpreted as SQL
    with pytest.raises(ValueError, match="존재하지 않는 컬럼"):
        bi.query_dataset(dataset_id, DatasetQuery(dimension='k"; DROP TABLE x; --', measure="v"))


def test_scatter_sample_is_deterministic_and_bounded(publish) -> None:
    dataset_id = publish(pd.DataFrame({"x": range(500), "y": range(500)}))
    request = DatasetChartRequest(chart_type="scatter", x="x", y="y", sample_limit=100, seed=7)
    first, second = bi.build_chart(dataset_id, request), bi.build_chart(dataset_id, request)
    assert first.sample_size == 100
    assert first.chart_spec["series"][0]["data"] == second.chart_spec["series"][0]["data"]


def test_scatter_keeps_all_rows_below_the_sample_limit_and_skips_nulls(publish) -> None:
    dataset_id = publish(pd.DataFrame({"x": [1.0, 2.0, None], "y": [3.0, None, 5.0]}))
    result = bi.build_chart(dataset_id, DatasetChartRequest(chart_type="scatter", x="x", y="y"))
    assert result.sample_size == 1 and result.chart_spec["series"][0]["data"] == [[1.0, 3.0]]


def test_histogram_matches_numpy(publish) -> None:
    values = np.random.default_rng(3).normal(50, 10, 1_000)
    dataset_id = publish(pd.DataFrame({"x": values}))
    result = bi.build_chart(dataset_id, DatasetChartRequest(chart_type="histogram", x="x", bins=12))
    expected, _ = np.histogram(values, bins=12)
    assert result.chart_spec["series"][0]["data"] == expected.tolist()
    assert result.sample_size == 1_000


def test_histogram_of_a_constant_column_and_of_nothing(publish) -> None:
    constant = bi.build_chart(publish(pd.DataFrame({"x": [5.0, 5.0, 5.0]})), DatasetChartRequest(chart_type="histogram", x="x", bins=5))
    assert sum(constant.chart_spec["series"][0]["data"]) == 3
    nothing = pd.DataFrame({"x": [None, None]}, dtype="float64")
    empty = bi.build_chart(publish(nothing), DatasetChartRequest(chart_type="histogram", x="x", bins=5))
    assert empty.sample_size == 0 and empty.chart_spec["series"][0]["data"] == [0] * 5


def test_boxplot_quantiles_match_numpy(publish) -> None:
    frame = pd.DataFrame({"g": ["a"] * 5 + ["b"] * 4, "x": [1.0, 2.0, 3.0, 4.0, 10.0, 5.0, 6.0, 7.0, 8.0]})
    result = bi.build_chart(publish(frame), DatasetChartRequest(chart_type="boxplot", x="x", group="g"))
    spec = result.chart_spec
    assert spec["xAxis"]["data"] == ["a", "b"]  # larger group first
    for label, box in zip(spec["xAxis"]["data"], spec["series"][0]["data"], strict=True):
        expected = np.quantile(frame.loc[frame["g"] == label, "x"], [0, 0.25, 0.5, 0.75, 1]).tolist()
        assert box == pytest.approx(expected)
    assert result.sample_size == 9


def test_boxplot_keeps_only_the_thirty_largest_groups(publish) -> None:
    frame = pd.DataFrame({"g": [f"g{index:02d}" for index in range(40) for _ in range(2)], "x": [1.0] * 80})
    result = bi.build_chart(publish(frame), DatasetChartRequest(chart_type="boxplot", x="x", group="g"))
    assert len(result.chart_spec["xAxis"]["data"]) == 30


def test_heatmap_counts_match_a_crosstab(publish) -> None:
    frame = pd.DataFrame({"a": ["x", "x", "y", "y", "y"], "b": ["p", "q", "p", "p", "q"]})
    result = bi.build_chart(publish(frame), DatasetChartRequest(chart_type="heatmap", x="a", y="b"))
    spec = result.chart_spec
    xs, ys = spec["xAxis"]["data"], spec["yAxis"]["data"]
    counts = {(xs[x], ys[y]): count for x, y, count in spec["series"][0]["data"]}
    expected = pd.crosstab(frame["b"], frame["a"])
    for (a, b), count in counts.items():
        assert count == expected.loc[b, a]
    assert result.sample_size == 5 and spec["visualMap"]["max"] == 2


def test_chart_requirements_are_validated(publish) -> None:
    dataset_id = publish(pd.DataFrame({"a": [1.0], "b": [2.0]}))
    for chart_type in ("scatter", "heatmap"):
        with pytest.raises(ValueError):
            bi.build_chart(dataset_id, DatasetChartRequest(chart_type=chart_type, x="a"))
    with pytest.raises(ValueError):
        bi.build_chart(dataset_id, DatasetChartRequest(chart_type="boxplot", x="a"))
    with pytest.raises(ValueError, match="존재하지 않는 컬럼"):
        bi.build_chart(dataset_id, DatasetChartRequest(chart_type="histogram", x="nope"))


def test_metrics_can_be_updated_and_recomputed_from_current_version(publish) -> None:
    dataset_id = publish(pd.DataFrame({"revenue": [100.0, 200.0], "spend": [50.0, 100.0]}))

    created = bi.create_metric(
        MetricWrite(name="ROAS", dataset_id=dataset_id, aggregation="ratio", numerator="revenue", denominator="spend", unit="x")
    )
    updated = bi.create_metric(MetricWrite(name="ROAS", dataset_id=dataset_id, aggregation="mean", column="revenue", unit="KRW"))

    assert created.value == 2.0 and updated.value == 150.0
    metrics = bi.list_metrics(dataset_id)
    assert len(metrics) == 1 and metrics[0].unit == "KRW" and metrics[0].value == 150.0


def test_metric_edge_cases(publish) -> None:
    dataset_id = publish(pd.DataFrame({"a": [None, None], "z": [0.0, 0.0], "n": [1.0, 2.0]}, dtype="float64"))

    def value(name: str, **kwargs) -> float:
        return bi.create_metric(MetricWrite(name=name, dataset_id=dataset_id, **kwargs)).value

    assert value("sum-empty", aggregation="sum", column="a") == 0.0
    assert np.isnan(value("mean-empty", aggregation="mean", column="a"))
    assert np.isnan(value("ratio-zero", aggregation="ratio", numerator="n", denominator="z"))
    assert value("rows", aggregation="count") == 2.0
    assert value("non-null", aggregation="count", column="a") == 0.0
    with pytest.raises(ValueError, match="존재하지 않는 컬럼"):
        value("bad", aggregation="sum", column="missing")
    with pytest.raises(KeyError):
        bi.create_metric(MetricWrite(name="x", dataset_id="nope", aggregation="count"))
