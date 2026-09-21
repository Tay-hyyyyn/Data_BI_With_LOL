from __future__ import annotations

import pandas as pd
import pytest
from app.lol.benchmark import normalize_lolps_benchmark


def test_lolps_manual_benchmark_normalizes_percentages_and_aliases() -> None:
    result = normalize_lolps_benchmark(pd.DataFrame([{
        "version": "16.18", "champion": "Ahri", "item": "Luden",
        "games": 1000, "winrate": 52.3, "pickrate": 12.5,
    }]))
    assert result.iloc[0]["win_rate"] == pytest.approx(0.523)
    assert result.iloc[0]["pick_rate"] == pytest.approx(0.125)
    assert result.iloc[0]["benchmark_source"] == "lol.ps-manual"


def test_lolps_manual_benchmark_requires_aggregate_metric() -> None:
    with pytest.raises(ValueError, match="집계 지표"):
        normalize_lolps_benchmark(pd.DataFrame([{"champion": "Ahri", "item": "Luden"}]))
