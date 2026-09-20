"""Safely expand the private LoL Match-V5 sample from already collected games.

This is intentionally conservative for a Riot Development API key: it discovers
recent matches from a few existing participants, de-duplicates match IDs, and
persists at most 30 new games per execution.  It never publishes Riot data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "backend"))

from app.config import settings  # noqa: E402
from app.lol.client import RiotClient, RiotKeyError  # noqa: E402
from app.main import app  # noqa: E402


def _existing_match_ids() -> list[str]:
    root = settings.root / "bronze" / "riot" / "matches"
    if not root.is_dir():
        return []
    return sorted(
        directory.name
        for directory in root.iterdir()
        if directory.is_dir()
        and (directory / "match.json").is_file()
        and (directory / "timeline.json").is_file()
    )


def _seed_puuids(match_ids: list[str], limit: int) -> list[str]:
    root = settings.root / "bronze" / "riot" / "matches"
    seeds: set[str] = set()
    for match_id in match_ids:
        payload = json.loads((root / match_id / "match.json").read_text("utf-8"))
        for participant in payload.get("info", {}).get("participants", []):
            if participant.get("puuid"):
                seeds.add(str(participant["puuid"]))
    return sorted(seeds)[:limit]


async def _collect_new_matches(seed_puuids: list[str], existing: set[str], maximum: int) -> tuple[list[str], int]:
    client = RiotClient()
    candidates: list[str] = []
    seen = set(existing)
    for puuid in seed_puuids:
        for match_id in await client.match_ids(puuid, count=20):
            if match_id not in seen:
                candidates.append(match_id)
                seen.add(match_id)
                if len(candidates) >= maximum:
                    break
        if len(candidates) >= maximum:
            break

    fetched = 0
    for match_id in candidates:
        await client.persist_match(match_id)
        fetched += 1
    return candidates, fetched


def _require_ok(response, step: str) -> dict:
    if response.is_success:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    raise RuntimeError(f"{step} 실패 ({response.status_code}): {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="기존 LoL 표본의 참가자에서 안전하게 추가 Match-V5 표본을 수집합니다.")
    parser.add_argument("--max-new-matches", type=int, default=30, choices=range(1, 41))
    parser.add_argument("--seed-limit", type=int, default=10, choices=range(1, 21))
    args = parser.parse_args()

    before = _existing_match_ids()
    seeds = _seed_puuids(before, args.seed_limit)
    if not seeds:
        raise SystemExit("기존 Riot 경기 표본이 없습니다. collect_lol_sample.py를 먼저 실행하세요.")

    try:
        new_match_ids, fetched = asyncio.run(_collect_new_matches(seeds, set(before), args.max_new_matches))
    except RiotKeyError as error:
        raise SystemExit(
            f"Riot API 요청을 시작하지 못했습니다: {error}\n"
            "Developer Portal에서 Development Key를 재발급한 뒤 .env의 RIOT_API_KEY를 갱신하고 다시 실행하세요."
        ) from error
    all_match_ids = sorted(set(before).union(new_match_ids))
    with TestClient(app) as client:
        processed = _require_ok(
            client.post(
                "/api/v1/lol/matches/process-grouped",
                json={"match_ids": all_match_ids, "snapshot_minutes": [10, 15, 20]},
            ),
            "패치별 분석 마트 생성",
        )

    print(
        json.dumps(
            {
                "visibility": "private",
                "existing_matches": len(before),
                "seed_players_used": len(seeds),
                "new_matches": len(new_match_ids),
                "fetched": fetched,
                "total_matches_processed": len(all_match_ids),
                "patches": sorted(processed["patches"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
