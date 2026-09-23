"""BI marts built from normalized Match-V5/Timeline data. Pure pandas — no FastAPI, no SQLite."""

from __future__ import annotations

import pandas as pd

from .items import REFERENCE_ITEMS
from .static import patch_key


def _patch_column(frame: pd.DataFrame) -> pd.Series:
    """The 2-segment patch (e.g. "16.18") derived from `game_version`, via the same `patch_key`
    used everywhere else a patch is derived from a Data Dragon or Match-V5 version string —
    `build_gold_win_timeseries` used to group on the full `game_version` while its sibling marts
    grouped on this 2-segment key, fragmenting one patch's build numbers into separate rows."""
    return frame["game_version"].astype(str).map(patch_key)


def build_context_mart(states: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    if states.empty:
        return states.copy()
    price = items.set_index("item_id")["total_gold"].to_dict()
    names = items.set_index("item_id")["item_name"].to_dict()
    output = states.copy()
    parsed = output["inventory"].fillna("").map(lambda value: [int(item) for item in str(value).split(",") if item])
    output["inventory_cost"] = parsed.map(lambda inventory: float(sum(price.get(item, 0) for item in inventory)))
    output["item_names"] = parsed.map(lambda inventory: ", ".join(str(names.get(item, item)) for item in inventory))
    # Match-V5 timeline frames do not expose the champion's complete combat stat
    # vector.  Keep these names explicit: they are the stats supplied by the
    # current inventory, not base/growth/rune/buff-inclusive champion stats.
    for stat in REFERENCE_ITEMS:
        if stat not in items.columns:
            continue
        values = items.set_index("item_id")[stat].fillna(0).to_dict()
        output[f"inventory_{stat}"] = parsed.map(
            lambda inventory, lookup=values: float(sum(lookup.get(item, 0) for item in inventory))
        )
    team_gold = output.groupby(["match_id", "minute", "team_id"], dropna=False)["total_gold"].sum().rename("team_total_gold").reset_index()
    output = output.merge(team_gold, on=["match_id", "minute", "team_id"], how="left")
    matchup = team_gold.merge(team_gold, on=["match_id", "minute"], suffixes=("", "_opponent"))
    matchup = matchup.loc[matchup["team_id"] != matchup["team_id_opponent"], ["match_id", "minute", "team_id", "team_total_gold_opponent"]]
    output = output.merge(matchup, on=["match_id", "minute", "team_id"], how="left")
    output["team_gold_diff"] = output["team_total_gold"] - output["team_total_gold_opponent"]
    lane = output[["match_id", "minute", "team_id", "role", "total_gold"]].merge(
        output[["match_id", "minute", "team_id", "role", "total_gold"]], on=["match_id", "minute", "role"], suffixes=("", "_opponent")
    )
    lane = lane.loc[lane["team_id"] != lane["team_id_opponent"], ["match_id", "minute", "team_id", "role", "total_gold_opponent"]]
    output = output.merge(lane.drop_duplicates(["match_id", "minute", "team_id", "role"]), on=["match_id", "minute", "team_id", "role"], how="left")
    output["lane_gold_diff"] = output["total_gold"] - output["total_gold_opponent"]
    output["observed_win"] = output["win"].astype(int)
    return output


def build_gold_win_timeseries(context: pd.DataFrame, bucket_size: int = 500) -> pd.DataFrame:
    """Build descriptive (not causal) win-rate cohorts by patch, minute, role and player gold."""
    if context.empty:
        return context.copy()
    if bucket_size <= 0:
        raise ValueError("골드 구간 크기는 0보다 커야 합니다.")
    output = context.copy()
    output["patch"] = _patch_column(output)
    output["gold_bucket_start"] = (output["total_gold"].fillna(0) // bucket_size * bucket_size).astype(int)
    output["gold_bucket_end"] = output["gold_bucket_start"] + bucket_size - 1
    dimensions = ["patch", "minute", "role", "gold_bucket_start", "gold_bucket_end"]
    aggregations: dict[str, tuple[str, str]] = {
        "sample_players": ("participant_id", "count"),
        "sample_matches": ("match_id", "nunique"),
        "observed_win_rate": ("observed_win", "mean"),
        "average_total_gold": ("total_gold", "mean"),
        "average_inventory_cost": ("inventory_cost", "mean"),
        "average_team_gold_diff": ("team_gold_diff", "mean"),
        "average_lane_gold_diff": ("lane_gold_diff", "mean"),
    }
    for column in output.columns:
        if column.startswith("inventory_") and column not in {"inventory_cost"}:
            aggregations[f"average_{column}"] = (column, "mean")
    return output.groupby(dimensions, dropna=False).agg(**aggregations).reset_index()


def build_patch_stat_trend(context: pd.DataFrame) -> pd.DataFrame:
    """Summarize compatible patch-specific context marts for cross-patch BI."""
    if context.empty:
        return context.copy()
    output = context.copy()
    output["patch"] = _patch_column(output)
    aggregations: dict[str, tuple[str, str]] = {
        "sample_players": ("participant_id", "count"),
        "sample_matches": ("match_id", "nunique"),
        "observed_win_rate": ("observed_win", "mean"),
        "average_total_gold": ("total_gold", "mean"),
        "average_inventory_cost": ("inventory_cost", "mean"),
        "average_team_gold_diff": ("team_gold_diff", "mean"),
        "average_lane_gold_diff": ("lane_gold_diff", "mean"),
    }
    for column in output.columns:
        if column.startswith("inventory_") and column != "inventory_cost":
            aggregations[f"average_{column}"] = (column, "mean")
    return output.groupby(["patch", "minute"], dropna=False).agg(**aggregations).reset_index()


def build_sample_coverage(context: pd.DataFrame) -> pd.DataFrame:
    """Expose sample composition and data completeness for BI quality monitoring."""
    if context.empty:
        return context.copy()
    output = context.copy()
    output["patch"] = _patch_column(output)
    output["inventory_missing"] = output["inventory"].fillna("").astype(str).eq("")
    return (
        output.groupby(["patch", "minute", "role"], dropna=False)
        .agg(
            sample_players=("participant_id", "count"),
            sample_matches=("match_id", "nunique"),
            sample_champions=("champion_id", "nunique"),
            observed_win_rate=("observed_win", "mean"),
            average_total_gold=("total_gold", "mean"),
            inventory_missing_ratio=("inventory_missing", "mean"),
        )
        .reset_index()
    )


def build_observed_win_summary(context: pd.DataFrame) -> pd.DataFrame:
    if context.empty:
        return context.copy()
    group_columns = ["game_version", "minute", "champion_id", "role", "item_names"]
    return (
        context.groupby(group_columns, dropna=False)
        .agg(
            sample_players=("participant_id", "count"),
            sample_matches=("match_id", "nunique"),
            observed_win_rate=("observed_win", "mean"),
            average_inventory_cost=("inventory_cost", "mean"),
            average_team_gold_diff=("team_gold_diff", "mean"),
            average_lane_gold_diff=("lane_gold_diff", "mean"),
        )
        .reset_index()
    )


def build_item_event_mart(events: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    item_columns = ["item_id", "item_name", "total_gold", "item_tier", "is_final_item"]
    available = [column for column in item_columns if column in items.columns]
    output = events.merge(items[available].drop_duplicates("item_id"), on="item_id", how="left")
    output["minute"] = output["timestamp_ms"] / 60_000
    final_item = output["is_final_item"].eq(True) if "is_final_item" in output else pd.Series(False, index=output.index)
    output["is_completion_event"] = output["event_type"].eq("ITEM_PURCHASED") & final_item
    return output
