from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "backend"))

from app.config import settings  # noqa: E402
from app.lol.static import patch_key  # noqa: E402
from app.main import app  # noqa: E402


def _require_ok(response, step: str) -> dict:
    if response.is_success:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    raise RuntimeError(f"{step} 실패 ({response.status_code}): {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Riot ID의 최근 Match-V5/Timeline 표본을 비공개로 수집하고 분석 마트를 만듭니다.")
    parser.add_argument("riot_id", help="게임이름#태그 형식")
    parser.add_argument("--count", type=int, default=5, choices=range(1, 21))
    args = parser.parse_args()
    if "#" not in args.riot_id:
        raise SystemExit("Riot ID는 게임이름#태그 형식이어야 합니다.")
    game_name, tag_line = args.riot_id.rsplit("#", 1)

    with TestClient(app) as client:
        account = _require_ok(
            client.post("/api/v1/lol/accounts/resolve", json={"game_name": game_name, "tag_line": tag_line}),
            "Riot ID 확인",
        )
        collection = _require_ok(
            client.post("/api/v1/lol/matches/collect", json={"puuid": account["puuid"], "count": args.count}),
            "경기 수집",
        )
        match_ids = [item["match_id"] for item in collection["matches"]]
        if not match_ids:
            raise RuntimeError("수집할 최근 경기가 없습니다.")

        matches_by_patch: dict[str, list[str]] = {}
        for match_id in match_ids:
            match = json.loads(
                (settings.root / "bronze" / "riot" / "matches" / match_id / "match.json").read_text("utf-8")
            )
            match_patch = patch_key(str(match.get("info", {}).get("gameVersion", "")))
            matches_by_patch.setdefault(match_patch, []).append(match_id)
        datasets = _require_ok(client.get("/api/v1/datasets"), "데이터셋 조회")
        processed_by_patch = {}
        for match_patch, patch_match_ids in sorted(matches_by_patch.items()):
            item_dataset = next(
                (
                    dataset for dataset in datasets
                    if dataset["source_type"] == "riot-data-dragon"
                    and dataset["name"].startswith("LoL items ")
                    and patch_key(dataset["name"].removeprefix("LoL items ")) == match_patch
                ),
                None,
            )
            if item_dataset is None:
                requested_version = f"{match_patch}.1"
                synced = _require_ok(
                    client.post("/api/v1/lol/static/sync", json={"version": requested_version, "bootstrap_samples": 200}),
                    f"Data Dragon {requested_version} 동기화",
                )
                item_dataset = synced["items"]
                datasets.append(item_dataset)
            processed_by_patch[match_patch] = _require_ok(
                client.post(
                    "/api/v1/lol/matches/process",
                    json={"match_ids": patch_match_ids, "snapshot_minutes": [10, 15, 20], "item_dataset_id": item_dataset["id"]},
                ),
                f"{match_patch} 분석 마트 생성",
            )
    print(json.dumps({
        "riot_id": f"{game_name}#{tag_line}",
        "patches": {patch: len(ids) for patch, ids in matches_by_patch.items()},
        "matches": len(match_ids),
        "fetched": collection["fetched"],
        "cached": collection["cached"],
        "datasets": {
            patch: {name: {"id": value["id"], "rows": value["row_count"]} for name, value in processed.items()}
            for patch, processed in processed_by_patch.items()
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
