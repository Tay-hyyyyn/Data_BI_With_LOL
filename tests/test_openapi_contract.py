from __future__ import annotations

from app.main import app


def test_query_result_contract_exposes_stable_row_shape() -> None:
    schemas = app.openapi()["components"]["schemas"]

    row = schemas["DatasetQueryRow"]
    assert set(row["properties"]) == {"category", "series", "value"}
    assert row["required"] == ["value"]

    query_result = schemas["DatasetQueryResult"]
    assert query_result["properties"]["rows"]["items"]["$ref"] == "#/components/schemas/DatasetQueryRow"
