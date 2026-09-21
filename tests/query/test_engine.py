from __future__ import annotations

import pytest
from app.query import materialize, schema_of


def test_materialize_full_frame(client, dataset):
    frame = materialize(dataset["id"])
    assert len(frame) == dataset["row_count"]
    assert "revenue" in frame.columns


def test_materialize_projects_columns_and_limits_rows(client, dataset):
    frame = materialize(dataset["id"], columns=["channel", "revenue"], limit=7)
    assert list(frame.columns) == ["channel", "revenue"]
    assert len(frame) == 7


def test_materialize_rejects_unknown_column_without_reaching_sql(client, dataset):
    with pytest.raises(ValueError):
        materialize(dataset["id"], columns=['revenue"; DROP TABLE x; --'])


def test_unknown_dataset_raises_key_error(client):
    with pytest.raises(KeyError):
        materialize("missing")


def test_schema_of_returns_duckdb_types(client, dataset):
    schema = schema_of(dataset["id"])
    assert set(schema) >= {"channel", "revenue", "date"}
    assert schema["revenue"].upper().startswith("DOUBLE")
