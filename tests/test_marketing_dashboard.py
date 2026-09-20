from __future__ import annotations

import pandas as pd
import pytest

from app.services import bi


def test_marketing_starter_dashboard_creates_editable_typed_widgets(monkeypatch) -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01"]), "channel": ["Social"],
        "spend": [100.0], "impressions": [1_000], "clicks": [50],
        "conversions": [5], "revenue": [500.0], "roas": [5.0],
    })
    captured = {}
    monkeypatch.setattr(bi, "read_frame", lambda _: frame)
    monkeypatch.setattr(bi, "save_or_update_dashboard", lambda name, widgets, filters=None: captured.update(name=name, widgets=widgets, filters=filters) or {"name": name})

    result = bi.create_marketing_starter_dashboard("marketing-id")

    assert result["name"] == "마케팅 성과 시작 대시보드 · marketin"
    assert len(captured["widgets"]) == 6
    assert captured["widgets"][2]["column"] == "roas"
    assert captured["widgets"][3]["series"] == "channel"


def test_marketing_starter_dashboard_rejects_incompatible_schema(monkeypatch) -> None:
    monkeypatch.setattr(bi, "read_frame", lambda _: pd.DataFrame({"spend": [1]}))

    with pytest.raises(ValueError, match="마케팅 시작 대시보드"):
        bi.create_marketing_starter_dashboard("incomplete")
