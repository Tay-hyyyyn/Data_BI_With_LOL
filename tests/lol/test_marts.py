from __future__ import annotations

import pandas as pd
from app.lol.items import item_frame
from app.lol.marts import (
    build_context_mart,
    build_gold_win_timeseries,
    build_item_event_mart,
    build_observed_win_summary,
    build_patch_stat_trend,
    build_sample_coverage,
)
from app.lol.pricing import reference_prices


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
    assert {"patch", "gold_bucket_start", "gold_bucket_end", "observed_win_rate", "average_inventory_ad"}.issubset(timeseries.columns)
    assert timeseries["sample_players"].sum() == len(mart)
    assert (timeseries["patch"] == "16.18").all()
    trend = build_patch_stat_trend(mart)
    assert {"patch", "minute", "average_inventory_ad", "sample_matches"}.issubset(trend.columns)
    assert trend.iloc[0]["patch"] == "16.18"
    coverage = build_sample_coverage(mart)
    assert {"patch", "role", "sample_players", "inventory_missing_ratio"}.issubset(coverage.columns)
    assert coverage["sample_players"].sum() == len(mart)


def test_timeseries_and_trend_agree_on_patch_granularity_across_build_numbers() -> None:
    """Regression: build_gold_win_timeseries used to group by the full game_version string
    (fragmenting one patch's build numbers into separate rows) while its sibling marts grouped
    by the 2-segment patch key."""
    mart = pd.DataFrame(
        [
            {"match_id": "KR_1", "minute": 10, "role": "TOP", "total_gold": 3000, "inventory_cost": 0, "team_gold_diff": 0, "lane_gold_diff": 0, "observed_win": 1, "participant_id": 1, "game_version": "16.18.712.1234", "champion_id": 1, "inventory": ""},
            {"match_id": "KR_2", "minute": 10, "role": "TOP", "total_gold": 3200, "inventory_cost": 0, "team_gold_diff": 0, "lane_gold_diff": 0, "observed_win": 0, "participant_id": 2, "game_version": "16.18.900.5678", "champion_id": 2, "inventory": ""},
        ]
    )

    timeseries = build_gold_win_timeseries(mart, bucket_size=500)
    trend = build_patch_stat_trend(mart)

    assert set(timeseries["patch"]) == {"16.18"}
    assert set(trend["patch"]) == {"16.18"}
    assert timeseries["sample_matches"].iloc[0] == 2  # both build numbers merged into one patch row


def test_item_event_mart_marks_final_item_purchase() -> None:
    events = pd.DataFrame([{"match_id": "KR_1", "participant_id": 1, "timestamp_ms": 900_000, "event_type": "ITEM_PURCHASED", "item_id": 6655}])
    items = pd.DataFrame([{"item_id": 6655, "item_name": "Luden", "total_gold": 2900, "item_tier": 3, "is_final_item": True}])

    mart = build_item_event_mart(events, items)

    assert mart.iloc[0]["minute"] == 15
    assert bool(mart.iloc[0]["is_completion_event"])
