from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from scipy.optimize import nnls


STAT_KEYS = {
    "FlatPhysicalDamageMod": "ad",
    "FlatMagicDamageMod": "ap",
    "FlatHPPoolMod": "hp",
    "FlatArmorMod": "armor",
    "FlatSpellBlockMod": "magic_resist",
    "PercentAttackSpeedMod": "attack_speed",
    "FlatCritChanceMod": "crit_chance",
    "FlatMovementSpeedMod": "move_speed",
    "FlatMPPoolMod": "mana",
}
REFERENCE_ITEMS = {
    "ad": "Long Sword",
    "ap": "Amplifying Tome",
    "hp": "Ruby Crystal",
    "armor": "Cloth Armor",
    "magic_resist": "Null-Magic Mantle",
    "ability_haste": "Glowing Mote",
    "attack_speed": "Dagger",
    "crit_chance": "Cloak of Agility",
    "move_speed": "Boots",
    "mana": "Sapphire Crystal",
}


def _ability_haste(description: str) -> float:
    plain = re.sub(r"<[^>]+>", " ", description)
    match = re.search(r"(?:Ability Haste\s*\+?\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*Ability Haste)", plain, re.I)
    return float(next(value for value in match.groups() if value)) if match else 0.0


def item_frame(payload: dict[str, Any], patch: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item_id, item in payload.get("data", {}).items():
        if not item.get("gold", {}).get("purchasable") or not item.get("maps", {}).get("11", False):
            continue
        row: dict[str, Any] = {
            "patch": patch,
            "item_id": int(item_id),
            "item_name": item.get("name", item_id),
            "total_gold": float(item.get("gold", {}).get("total", 0)),
            "description": item.get("description", ""),
            "tags": ",".join(item.get("tags", [])),
            "item_tier": int(item.get("depth", 1) or 1),
            "is_final_item": not bool(item.get("into")),
        }
        row.update({name: float(item.get("stats", {}).get(key, 0)) for key, name in STAT_KEYS.items()})
        row["ability_haste"] = _ability_haste(row["description"])
        rows.append(row)
    return pd.DataFrame(rows)


def reference_prices(items: pd.DataFrame) -> dict[str, float]:
    result: dict[str, float] = {}
    for stat, item_name in REFERENCE_ITEMS.items():
        row = items.loc[items["item_name"].eq(item_name)]
        if row.empty or float(row.iloc[0].get(stat, 0)) <= 0:
            continue
        result[stat] = float(row.iloc[0]["total_gold"] / row.iloc[0][stat])
    return result


def estimate_gold_values(items: pd.DataFrame, alpha: float = 10.0, bootstrap: int = 200, seed: int = 42) -> pd.DataFrame:
    stat_columns = [name for name in REFERENCE_ITEMS if name in items and items[name].fillna(0).abs().sum() > 0]
    model_data = items.loc[items["total_gold"] > 0, stat_columns + ["total_gold"]].fillna(0)
    if len(model_data) < len(stat_columns) + 2:
        raise ValueError("회귀 모델을 계산할 아이템 표본이 부족합니다.")
    model = Ridge(alpha=alpha, positive=True, fit_intercept=True).fit(model_data[stat_columns], model_data["total_gold"])
    nnls_coefficients, _ = nnls(model_data[stat_columns].to_numpy(dtype=float), model_data["total_gold"].to_numpy(dtype=float))
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(bootstrap):
        positions = rng.integers(0, len(model_data), len(model_data))
        boot = model_data.iloc[positions]
        samples.append(Ridge(alpha=alpha, positive=True).fit(boot[stat_columns], boot["total_gold"]).coef_)
    estimates = np.asarray(samples)
    references = reference_prices(items)
    return pd.DataFrame({
        "stat": stat_columns,
        "reference_gold_per_unit": [references.get(name, np.nan) for name in stat_columns],
        "ridge_gold_per_unit": model.coef_,
        "nnls_gold_per_unit": nnls_coefficients,
        "ci95_low": np.quantile(estimates, 0.025, axis=0),
        "ci95_high": np.quantile(estimates, 0.975, axis=0),
        "sample_items": len(model_data),
    })


def item_efficiency(items: pd.DataFrame, prices: dict[str, float]) -> pd.DataFrame:
    output = items.copy()
    output["estimated_stat_value"] = sum(output.get(stat, 0) * value for stat, value in prices.items())
    output["gold_efficiency_percent"] = np.where(output["total_gold"] > 0, output["estimated_stat_value"] / output["total_gold"] * 100, np.nan)
    output["passive_shadow_price"] = output["total_gold"] - output["estimated_stat_value"]
    return output


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
    """Build descriptive (not causal) win-rate cohorts by minute and player gold."""
    if context.empty:
        return context.copy()
    if bucket_size <= 0:
        raise ValueError("골드 구간 크기는 0보다 커야 합니다.")
    output = context.copy()
    output["gold_bucket_start"] = (output["total_gold"].fillna(0) // bucket_size * bucket_size).astype(int)
    output["gold_bucket_end"] = output["gold_bucket_start"] + bucket_size - 1
    dimensions = ["game_version", "minute", "role", "gold_bucket_start", "gold_bucket_end"]
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
    final_item = output["is_final_item"].fillna(False) if "is_final_item" in output else pd.Series(False, index=output.index)
    output["is_completion_event"] = output["event_type"].eq("ITEM_PURCHASED") & final_item
    return output
