from __future__ import annotations

from app import mcp_server


def test_mcp_query_forwards_optional_series(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(mcp_server, "_post", lambda path, payload: captured.update(path=path, payload=payload) or {"rows": []})

    result = mcp_server.query_dataset.fn("dataset-1", "revenue", aggregation="mean", dimension="month", series="channel")

    assert result == {"rows": []}
    assert captured["path"] == "/datasets/dataset-1/query"
    assert captured["payload"]["series"] == "channel"
