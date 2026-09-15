from __future__ import annotations

from typing import Any

import pandas as pd


def patch_key(version: str | None) -> str:
    parts = str(version or "").split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else str(version or "")


def champion_frame(payload: dict[str, Any], patch: str) -> pd.DataFrame:
    rows = []
    for champion in payload.get("data", {}).values():
        stats = champion.get("stats", {})
        rows.append(
            {
                "patch": patch,
                "champion_id": int(champion["key"]),
                "champion_key": champion.get("id"),
                "champion_name": champion.get("name"),
                "tags": ",".join(champion.get("tags", [])),
                **{f"base_{name}": value for name, value in stats.items()},
            }
        )
    return pd.DataFrame(rows)


def rune_frame(payload: list[dict[str, Any]], patch: str) -> pd.DataFrame:
    rows = []
    for tree in payload:
        for slot_index, slot in enumerate(tree.get("slots", [])):
            for rune in slot.get("runes", []):
                rows.append(
                    {
                        "patch": patch,
                        "tree_id": tree.get("id"),
                        "tree_name": tree.get("name"),
                        "slot": slot_index,
                        "rune_id": rune.get("id"),
                        "rune_key": rune.get("key"),
                        "rune_name": rune.get("name"),
                        "description": rune.get("longDesc") or rune.get("shortDesc"),
                    }
                )
    return pd.DataFrame(rows)
