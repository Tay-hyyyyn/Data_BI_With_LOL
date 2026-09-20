from __future__ import annotations

from types import SimpleNamespace

from app.api import lol


def test_lol_starter_dashboard_uses_patch_specific_marts(monkeypatch) -> None:
    datasets = {
        "LoL contextual gold mart 16.18": SimpleNamespace(id="context-1818"),
        "LoL gold and stat win-rate timeseries 16.18": SimpleNamespace(id="timeseries-1818"),
    }
    monkeypatch.setattr(lol, "get_dataset_by_name", lambda name, _source: datasets.get(name))
    captured = {}

    def fake_save(name, widgets, filters=None):
        captured.update(name=name, widgets=widgets, filters=filters)
        return SimpleNamespace(name=name, widgets=widgets)

    monkeypatch.setattr(lol, "save_or_update_dashboard", fake_save)

    result = lol.create_lol_starter_dashboard(lol.LolStarterDashboardRequest(patch="16.18.1"))

    assert result.name == "LoL 분석 시작 대시보드 16.18"
    assert len(captured["widgets"]) == 6
    assert captured["widgets"][0]["dataset_id"] == "context-1818"
    assert captured["widgets"][4]["dataset_id"] == "timeseries-1818"
    assert captured["widgets"][4]["aggregation"] == "mean"


def test_lol_patch_trend_dashboard_uses_trend_and_coverage_marts(monkeypatch) -> None:
    datasets = {
        "LoL patch stat trend": SimpleNamespace(id="trend"),
        "LoL sample coverage": SimpleNamespace(id="coverage"),
    }
    monkeypatch.setattr(lol, "get_dataset_by_name", lambda name, _source: datasets.get(name))
    captured = {}
    monkeypatch.setattr(lol, "save_or_update_dashboard", lambda name, widgets, filters=None: captured.update(name=name, widgets=widgets) or SimpleNamespace(name=name, widgets=widgets))

    result = lol.create_lol_patch_trend_dashboard()

    assert result.name == "LoL 패치 비교·표본 품질 대시보드"
    assert len(captured["widgets"]) == 6
    assert all(widget["series"] == "patch" for widget in captured["widgets"])
    assert captured["widgets"][0]["dataset_id"] == "trend"
    assert captured["widgets"][4]["dataset_id"] == "coverage"


def test_lol_case_study_dashboard_combines_static_and_observational_marts(monkeypatch) -> None:
    datasets = {
        "LoL static stat value trend": SimpleNamespace(id="static"),
        "LoL patch stat trend": SimpleNamespace(id="trend"),
        "LoL sample coverage": SimpleNamespace(id="coverage"),
    }
    monkeypatch.setattr(lol, "get_dataset_by_name", lambda name, _source: datasets.get(name))
    monkeypatch.setattr(
        lol,
        "list_datasets",
        lambda: [
            SimpleNamespace(name="LoL gold and stat win-rate timeseries 16.17", id="observed-1717"),
            SimpleNamespace(name="LoL gold and stat win-rate timeseries 16.18", id="observed-1818"),
        ],
    )
    captured = {}
    monkeypatch.setattr(lol, "save_or_update_dashboard", lambda name, widgets, filters=None: captured.update(name=name, widgets=widgets) or SimpleNamespace(name=name, widgets=widgets))

    result = lol.create_lol_case_study_dashboard()

    assert result.name == "LoL 통합 사례 분석 · 정적가치와 관찰경기"
    assert len(captured["widgets"]) == 6
    assert captured["widgets"][0]["dataset_id"] == "static"
    assert captured["widgets"][4]["dataset_id"] == "coverage"
    assert captured["widgets"][5]["dataset_id"] == "observed-1818"
    assert "관찰 승률" in captured["widgets"][5]["title"]
