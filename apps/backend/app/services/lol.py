"""LoL orchestration: static data sync, match collection/processing and starter dashboards.

Extracted from the HTTP layer so routers stay thin. Pure domain logic lives in `app.lol`.
"""

from __future__ import annotations

import json

import httpx
import pandas as pd

from ..config import settings
from ..errors import DomainError, NotFoundError
from ..lol.benchmark import read_lolps_benchmark_upload
from ..lol.client import RiotClient, fetch_data_dragon_bundle
from ..lol.items import (
    build_context_mart,
    build_gold_win_timeseries,
    build_item_event_mart,
    build_observed_win_summary,
    build_patch_stat_trend,
    build_sample_coverage,
    estimate_gold_values,
    item_efficiency,
    item_frame,
    reference_prices,
)
from ..lol.static import champion_frame, patch_key, rune_frame
from ..lol.timeline import normalize_persisted
from ..schemas import (
    DashboardSummary,
    DatasetSummary,
    LolStarterDashboardRequest,
    LolStaticSyncRequest,
    RiotAccountResolveRequest,
    RiotAccountSummary,
    RiotMatchCollectRequest,
    RiotMatchProcessRequest,
)
from .bi import save_or_update_dashboard
from .datasets import create_dataset_from_frame, get_dataset_by_name, list_datasets, read_frame, sync_named_dataset


async def sync_static(request: LolStaticSyncRequest) -> dict:
    version, payload = await fetch_data_dragon_bundle(request.version)
    items = item_frame(payload["items"], version)
    champions = champion_frame(payload["champions"], version)
    runes = rune_frame(payload["runes"], version)
    estimates = estimate_gold_values(items, bootstrap=request.bootstrap_samples)
    efficiency = item_efficiency(items, reference_prices(items))
    item_dataset = sync_named_dataset(efficiency, f"LoL items {version}", "riot-data-dragon")
    champion_dataset = sync_named_dataset(champions, f"LoL champions {version}", "riot-data-dragon")
    rune_dataset = sync_named_dataset(runes, f"LoL runes {version}", "riot-data-dragon")
    value_dataset = sync_named_dataset(estimates, f"LoL stat values {version}", "riot-derived-model")
    return {"patch": version, "items": item_dataset, "champions": champion_dataset, "runes": rune_dataset, "stat_values": value_dataset}


def import_benchmark(filename: str, payload: bytes, name: str | None, sheet_name: str | None) -> DatasetSummary:
    frame = read_lolps_benchmark_upload(filename, payload, sheet_name)
    return create_dataset_from_frame(frame, name or "LOL.PS aggregate benchmark", "lolps-benchmark-manual")


def create_starter_dashboard(request: LolStarterDashboardRequest) -> DashboardSummary:
    patch = patch_key(request.patch)
    context = get_dataset_by_name(f"LoL contextual gold mart {patch}", "riot-derived-model")
    timeseries = get_dataset_by_name(f"LoL gold and stat win-rate timeseries {patch}", "riot-derived-model")
    if not context or not timeseries:
        raise NotFoundError(f"{patch} 패치의 분석 마트를 먼저 생성하세요.")

    def line(suffix: str, title: str, column: str, dimension: str, dataset_id: str) -> dict:
        return {
            "id": f"{patch}-{suffix}",
            "title": title,
            "type": "line",
            "column": column,
            "dimension": dimension,
            "aggregation": "mean",
            "dataset_id": dataset_id,
        }

    widgets = [
        line("gold", "분당 평균 보유 골드", "total_gold", "minute", context.id),
        line("ad", "분당 인벤토리 제공 AD", "inventory_ad", "minute", context.id),
        line("ap", "분당 인벤토리 제공 AP", "inventory_ap", "minute", context.id),
        line("haste", "분당 인벤토리 제공 스킬 가속", "inventory_ability_haste", "minute", context.id),
        line("gold-win", "골드 구간별 관찰 승률", "observed_win_rate", "gold_bucket_start", timeseries.id),
        {
            "id": f"{patch}-team-diff",
            "title": "팀 골드 격차와 관찰 승리",
            "type": "scatter",
            "column": "team_gold_diff",
            "secondary": "observed_win",
            "dataset_id": context.id,
        },
    ]
    return save_or_update_dashboard(f"LoL 분석 시작 대시보드 {patch}", widgets)


def create_patch_trend_dashboard() -> DashboardSummary:
    """Create a private dashboard that compares all processed LoL patches."""
    trend = get_dataset_by_name("LoL patch stat trend", "riot-derived-model")
    coverage = get_dataset_by_name("LoL sample coverage", "riot-derived-model")
    if not trend or not coverage:
        raise NotFoundError("패치별 경기 마트를 먼저 생성하세요.")

    def by_patch(widget_id: str, title: str, column: str, aggregation: str, dataset_id: str) -> dict:
        return {
            "id": widget_id,
            "title": title,
            "type": "line",
            "column": column,
            "dimension": "minute",
            "series": "patch",
            "aggregation": aggregation,
            "dataset_id": dataset_id,
        }

    widgets = [
        by_patch("patch-gold", "패치별 분당 평균 보유 골드", "average_total_gold", "mean", trend.id),
        by_patch("patch-ad", "패치별 분당 인벤토리 AD", "average_inventory_ad", "mean", trend.id),
        by_patch("patch-ap", "패치별 분당 인벤토리 AP", "average_inventory_ap", "mean", trend.id),
        by_patch("patch-ah", "패치별 분당 스킬 가속", "average_inventory_ability_haste", "mean", trend.id),
        by_patch("coverage-players", "패치별 시간대 표본 참가자 수", "sample_players", "sum", coverage.id),
        by_patch("coverage-inventory", "패치별 인벤토리 결측 비율", "inventory_missing_ratio", "mean", coverage.id),
    ]
    return save_or_update_dashboard("LoL 패치 비교·표본 품질 대시보드", widgets)


async def resolve_account(request: RiotAccountResolveRequest) -> RiotAccountSummary:
    try:
        account = await RiotClient().account_by_riot_id(request.game_name, request.tag_line)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise NotFoundError("Riot ID를 찾을 수 없습니다.") from error
        raise DomainError("Riot 계정 조회에 실패했습니다.", status_code=error.response.status_code) from error
    return RiotAccountSummary(
        puuid=account["puuid"],
        game_name=account.get("gameName", request.game_name),
        tag_line=account.get("tagLine", request.tag_line.lstrip("#")),
    )


async def collect_matches(request: RiotMatchCollectRequest) -> dict:
    client = RiotClient()
    match_ids = await client.match_ids(request.puuid, count=request.count)
    persisted = []
    for match_id in match_ids:
        directory = settings.root / "bronze" / "riot" / "matches" / match_id
        cached = (directory / "match.json").is_file() and (directory / "timeline.json").is_file()
        paths = await client.persist_match(match_id)
        persisted.append({"match_id": match_id, "cached": cached, "files": [str(path) for path in paths.values()]})
    return {
        "visibility": "private",
        "matches": persisted,
        "fetched": sum(not item["cached"] for item in persisted),
        "cached": sum(item["cached"] for item in persisted),
    }


def process_matches(request: RiotMatchProcessRequest) -> dict:
    participants, states, events = normalize_persisted(settings.root, request.match_ids, request.snapshot_minutes)
    patch_values = sorted({patch_key(str(value)) for value in participants.get("game_version", []) if value})
    patch_label = "-".join(patch_values) if patch_values else "unknown"
    result = {
        "participants": sync_named_dataset(participants, f"LoL match participants {patch_label}", "riot-match-v5"),
        "player_states": sync_named_dataset(states, f"LoL player state snapshots {patch_label}", "riot-timeline-v5"),
        "item_events": sync_named_dataset(events, f"LoL item events {patch_label}", "riot-timeline-v5"),
    }
    if request.item_dataset_id:
        items = read_frame(request.item_dataset_id)
        item_patch = patch_key(str(items.iloc[0]["patch"])) if "patch" in items and not items.empty else ""
        match_patches = {patch_key(value) for value in states.get("game_version", []) if value}
        if item_patch and any(value != item_patch for value in match_patches):
            raise ValueError(f"경기 패치 {sorted(match_patches)}와 아이템 패치 {item_patch}가 일치하지 않습니다.")
        mart = build_context_mart(states, items)
        mart["ddragon_version"] = str(items.iloc[0]["patch"]) if "patch" in items and not items.empty else None
        derived = "riot-derived-model"
        result["context_mart"] = sync_named_dataset(mart, f"LoL contextual gold mart {patch_label}", derived)
        result["observed_win_summary"] = sync_named_dataset(
            build_observed_win_summary(mart), f"LoL observed win cohorts {patch_label}", derived
        )
        result["gold_win_timeseries"] = sync_named_dataset(
            build_gold_win_timeseries(mart), f"LoL gold and stat win-rate timeseries {patch_label}", derived
        )
        result["item_event_mart"] = sync_named_dataset(
            build_item_event_mart(events, items), f"LoL item completion events {patch_label}", derived
        )
    return result


async def process_matches_grouped(request: RiotMatchProcessRequest) -> dict:
    """Process a mixed-patch collection safely rather than applying one item catalog to all games."""
    match_ids_by_patch: dict[str, list[str]] = {}
    for match_id in request.match_ids:
        path = settings.root / "bronze" / "riot" / "matches" / match_id / "match.json"
        if not path.is_file():
            raise FileNotFoundError(f"수집되지 않은 match_id: {match_id}")
        payload = json.loads(path.read_text("utf-8"))
        match_patch = patch_key(str(payload.get("info", {}).get("gameVersion", "")))
        match_ids_by_patch.setdefault(match_patch, []).append(match_id)

    processed: dict[str, dict] = {}
    context_frames = []
    for match_patch, patch_match_ids in sorted(match_ids_by_patch.items()):
        items = next(
            (
                dataset
                for dataset in list_datasets()
                if dataset.source_type == "riot-data-dragon"
                and dataset.name.startswith("LoL items ")
                and patch_key(dataset.name.removeprefix("LoL items ")) == match_patch
            ),
            None,
        )
        if not items:
            synced = await sync_static(LolStaticSyncRequest(version=f"{match_patch}.1"))
            items = synced["items"]
        result = process_matches(
            RiotMatchProcessRequest(
                match_ids=patch_match_ids,
                snapshot_minutes=request.snapshot_minutes,
                item_dataset_id=items.id,
            )
        )
        processed[match_patch] = result
        context_frames.append(read_frame(result["context_mart"].id))
    if not context_frames:
        return {"patches": processed}
    combined = pd.concat(context_frames, ignore_index=True)
    trend = sync_named_dataset(build_patch_stat_trend(combined), "LoL patch stat trend", "riot-derived-model")
    coverage = sync_named_dataset(build_sample_coverage(combined), "LoL sample coverage", "riot-derived-model")
    return {"patches": processed, "patch_stat_trend": trend, "sample_coverage": coverage}
