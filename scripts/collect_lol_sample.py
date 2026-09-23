from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "backend"))

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
    parser.add_argument("--count", type=int, default=20, choices=range(1, 101), metavar="[1-100]")
    parser.add_argument("--start", type=int, default=0, help="가장 최근 경기부터 건너뛸 개수 (페이징)")
    parser.add_argument("--queue", type=int, default=420, help="Match-V5 큐 ID. 기본값 420=솔로/듀오 랭크. 필터 없이 수집하려면 -1")
    parser.add_argument("--region", default="asia", choices=["americas", "asia", "europe", "sea"])
    args = parser.parse_args()
    if "#" not in args.riot_id:
        raise SystemExit("Riot ID는 게임이름#태그 형식이어야 합니다.")
    game_name, tag_line = args.riot_id.rsplit("#", 1)
    queue = None if args.queue < 0 else args.queue

    with TestClient(app) as client:
        account = _require_ok(
            client.post("/api/v1/lol/accounts/resolve", json={"game_name": game_name, "tag_line": tag_line, "region": args.region}),
            "Riot ID 확인",
        )
        collection = _require_ok(
            client.post(
                "/api/v1/lol/matches/collect",
                json={"puuid": account["puuid"], "count": args.count, "start": args.start, "queue": queue, "region": args.region},
            ),
            "경기 수집",
        )
        match_ids = [item["match_id"] for item in collection["matches"]]
        if not match_ids:
            raise RuntimeError("수집할 최근 경기가 없습니다.")

        # /process-grouped splits the batch by patch itself (and resolves each patch's real Data
        # Dragon version rather than guessing one), so there is nothing left to replicate here.
        processed = _require_ok(
            client.post("/api/v1/lol/matches/process-grouped", json={"match_ids": match_ids, "snapshot_minutes": [10, 15, 20]}),
            "패치별 분석 마트 생성",
        )

    print(
        json.dumps(
            {
                "riot_id": f"{game_name}#{tag_line}",
                "queue": queue,
                "matches": len(match_ids),
                "fetched": collection["fetched"],
                "cached": collection["cached"],
                "patches": {
                    patch: {name: {"id": value["id"], "rows": value["row_count"]} for name, value in datasets.items()}
                    for patch, datasets in processed["patches"].items()
                },
                "patch_stat_trend": processed.get("patch_stat_trend", {}).get("id"),
                "sample_coverage": processed.get("sample_coverage", {}).get("id"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
