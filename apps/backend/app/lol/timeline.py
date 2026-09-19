from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

import pandas as pd


def _subject_hash(puuid: str) -> str:
    pepper = os.getenv("DATA_BI_PUUID_PEPPER", "local-development-only").encode()
    return hmac.new(pepper, puuid.encode(), hashlib.sha256).hexdigest()


def normalize_match(match: dict, timeline: dict, snapshot_minutes: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata, info = match.get("metadata", {}), match.get("info", {})
    match_id = metadata.get("matchId", "unknown")
    participant_rows = []
    participants: dict[int, dict] = {}
    for participant in info.get("participants", []):
        pid = int(participant["participantId"])
        participants[pid] = participant
        participant_rows.append({
            "match_id": match_id, "participant_id": pid,
            "match_participant_key": f"{match_id}:{pid}",
            "puuid_hash": _subject_hash(participant.get("puuid", "")),
            "game_version": info.get("gameVersion"), "queue_id": info.get("queueId"),
            "champion_id": participant.get("championId"), "champion_name": participant.get("championName"),
            "team_id": participant.get("teamId"), "role": participant.get("teamPosition") or participant.get("individualPosition"),
            "win": bool(participant.get("win")), "kills": participant.get("kills"),
            "deaths": participant.get("deaths"), "assists": participant.get("assists"),
            "gold_earned": participant.get("goldEarned"), "game_duration_s": info.get("gameDuration"),
        })

    frames = timeline.get("info", {}).get("frames", [])
    item_events, inventory = [], {pid: [] for pid in participants}
    all_events = sorted((event for frame in frames for event in frame.get("events", [])), key=lambda event: event.get("timestamp", 0))
    for event in all_events:
        kind, pid = event.get("type"), event.get("participantId")
        if pid not in inventory or not str(kind).startswith("ITEM_"):
            continue
        item_id = int(event.get("itemId", 0) or 0)
        before = list(inventory[pid])
        if kind == "ITEM_PURCHASED" and item_id:
            inventory[pid].append(item_id)
        elif kind in {"ITEM_SOLD", "ITEM_DESTROYED"} and item_id in inventory[pid]:
            inventory[pid].remove(item_id)
        elif kind == "ITEM_UNDO":
            before_id, after_id = int(event.get("beforeId", 0) or 0), int(event.get("afterId", 0) or 0)
            if before_id in inventory[pid]: inventory[pid].remove(before_id)
            if after_id: inventory[pid].append(after_id)
        item_events.append({
            "match_id": match_id, "participant_id": pid, "timestamp_ms": event.get("timestamp", 0),
            "event_type": kind, "item_id": item_id, "inventory_before": ",".join(map(str, before)),
            "inventory_after": ",".join(map(str, inventory[pid])),
        })

    state_rows = []
    for minute in sorted(set(snapshot_minutes)):
        target = minute * 60_000
        available = [frame for frame in frames if frame.get("timestamp", 0) <= target]
        if not available:
            continue
        frame = available[-1]
        for raw_pid, state in frame.get("participantFrames", {}).items():
            pid = int(raw_pid)
            participant = participants.get(pid, {})
            inv = [event["inventory_after"] for event in item_events if event["participant_id"] == pid and event["timestamp_ms"] <= target]
            position = state.get("position", {})
            state_rows.append({
                "match_id": match_id, "participant_id": pid, "minute": minute,
                "match_participant_key": f"{match_id}:{pid}",
                "game_version": info.get("gameVersion"), "team_id": participant.get("teamId"),
                "champion_id": participant.get("championId"), "role": participant.get("teamPosition"), "win": bool(participant.get("win")),
                "total_gold": state.get("totalGold"), "current_gold": state.get("currentGold"),
                "level": state.get("level"), "xp": state.get("xp"), "cs": state.get("minionsKilled"),
                "jungle_cs": state.get("jungleMinionsKilled"), "position_x": position.get("x"), "position_y": position.get("y"),
                "inventory": inv[-1] if inv else "",
            })
    return pd.DataFrame(participant_rows), pd.DataFrame(state_rows), pd.DataFrame(item_events)


def normalize_persisted(root: Path, match_ids: list[str], snapshot_minutes: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    outputs = [[], [], []]
    for match_id in match_ids:
        directory = root / "bronze" / "riot" / "matches" / match_id
        if not (directory / "match.json").is_file() or not (directory / "timeline.json").is_file():
            raise FileNotFoundError(f"수집되지 않은 match_id: {match_id}")
        frames = normalize_match(json.loads((directory / "match.json").read_text("utf-8")), json.loads((directory / "timeline.json").read_text("utf-8")), snapshot_minutes)
        for bucket, frame in zip(outputs, frames): bucket.append(frame)
    return tuple(pd.concat(bucket, ignore_index=True) if bucket else pd.DataFrame() for bucket in outputs)  # type: ignore[return-value]
