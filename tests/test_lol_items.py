from __future__ import annotations

import pandas as pd

from app.lol.items import build_context_mart, build_gold_win_timeseries, build_item_event_mart, build_observed_win_summary, estimate_gold_values, item_frame, reference_prices


def test_reference_item_price_is_derived_from_payload() -> None:
    payload = {"data": {"1036": {"name": "Long Sword", "gold": {"purchasable": True, "total": 350}, "maps": {"11": True}, "stats": {"FlatPhysicalDamageMod": 10}, "description": ""}}}
    frame = item_frame(payload, "test")
    assert reference_prices(frame)["ad"] == 35.0


def test_context_mart_adds_inventory_and_gold_differences() -> None:
    states = pd.DataFrame(
        [
            {"match_id": "KR_1", "minute": 10, "team_id": 100, "role": "MIDDLE", "total_gold": 3500, "inventory": "1036", "win": True},
            {"match_id": "KR_1", "minute": 10, "team_id": 100, "role": "TOP", "total_gold": 3000, "inventory": "", "win": True},
            {"match_id": "KR_1", "minute": 10, "team_id": 200, "role": "MIDDLE", "total_gold": 3200, "inventory": "1056", "win": False},
            {"match_id": "KR_1", "minute": 10, "team_id": 200, "role": "TOP", "total_gold": 2900, "inventory": "", "win": False},
        ]
    )
    items = pd.DataFrame(
        [
            {"item_id": 1036, "item_name": "Long Sword", "total_gold": 350, "ad": 10, "ap": 0, "ability_haste": 0},
            {"item_id": 1056, "item_name": "Doran's Ring", "total_gold": 400, "ad": 0, "ap": 18, "ability_haste": 0},
        ]
    )

    mart = build_context_mart(states, items)
    middle = mart.loc[(mart["team_id"] == 100) & (mart["role"] == "MIDDLE")].iloc[0]

    assert middle["inventory_cost"] == 350
    assert middle["item_names"] == "Long Sword"
    assert middle["team_gold_diff"] == 400
    assert middle["lane_gold_diff"] == 300
    assert middle["observed_win"] == 1
    assert middle["inventory_ad"] == 10
    assert middle["inventory_ap"] == 0

    mart["game_version"] = "16.18.1"
    mart["champion_id"] = 1
    mart["participant_id"] = range(1, len(mart) + 1)
    summary = build_observed_win_summary(mart)
    assert {"sample_players", "sample_matches", "observed_win_rate"}.issubset(summary.columns)
    timeseries = build_gold_win_timeseries(mart, bucket_size=500)
    assert {"gold_bucket_start", "gold_bucket_end", "observed_win_rate", "average_inventory_ad"}.issubset(timeseries.columns)
    assert timeseries["sample_players"].sum() == len(mart)


def test_item_event_mart_marks_final_item_purchase() -> None:
    events = pd.DataFrame([{"match_id": "KR_1", "participant_id": 1, "timestamp_ms": 900_000, "event_type": "ITEM_PURCHASED", "item_id": 6655}])
    items = pd.DataFrame([{"item_id": 6655, "item_name": "Luden", "total_gold": 2900, "item_tier": 3, "is_final_item": True}])

    mart = build_item_event_mart(events, items)

    assert mart.iloc[0]["minute"] == 15
    assert bool(mart.iloc[0]["is_completion_event"])


def test_gold_model_exposes_non_negative_ridge_and_nnls() -> None:
    items = pd.DataFrame(
        {
            "item_name": ["A", "B", "C", "D", "E", "F"],
            "total_gold": [100, 200, 300, 400, 500, 600],
            "ad": [1, 2, 1, 3, 2, 4],
            "ap": [2, 1, 3, 1, 4, 2],
        }
    )
    result = estimate_gold_values(items, bootstrap=20)
    assert (result["ridge_gold_per_unit"] >= 0).all()
    assert (result["nnls_gold_per_unit"] >= 0).all()
