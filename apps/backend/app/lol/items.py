"""Data Dragon item catalog parsing. Pricing models live in `pricing.py`, marts in `marts.py`."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

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
