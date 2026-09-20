"""League of Legends example-domain API routes.

The generic BI core remains independent of Riot data.  These routes only adapt
Riot/Data Dragon inputs into the same versioned datasets and dashboards used by
the rest of the application.
"""

import json

import httpx
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import settings
from ..lol.benchmark import read_lolps_benchmark_upload
from ..lol.client import RiotClient, RiotKeyError, fetch_data_dragon_bundle
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
from ..services.bi import save_or_update_dashboard
from ..services.datasets import (
    create_dataset_from_frame,
    get_dataset_by_name,
    list_datasets,
    read_frame,
    sync_named_dataset,
)


router = APIRouter(tags=["lol"])


@router.post("/api/v1/lol/static/sync")
async def sync_lol_static(request: LolStaticSyncRequest) -> dict:
    try:
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
    except (ValueError, httpx.HTTPError) as error:
        raise HTTPException(502, str(error)) from error


@router.post("/api/v1/lol/benchmarks/upload", response_model=DatasetSummary, status_code=201)
async def upload_lolps_benchmark(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    sheet_name: str | None = Form(None),
) -> DatasetSummary:
    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(413, "파일 크기 제한을 초과했습니다.")
    try:
        frame = read_lolps_benchmark_upload(file.filename or "lolps-benchmark.csv", payload, sheet_name)
        return create_dataset_from_frame(frame, name or "LOL.PS aggregate benchmark", "lolps-benchmark-manual")
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/lol/dashboards/starter", response_model=DashboardSummary, status_code=201)
def create_lol_starter_dashboard(request: LolStarterDashboardRequest) -> DashboardSummary:
    patch = patch_key(request.patch)
    context = get_dataset_by_name(f"LoL contextual gold mart {patch}", "riot-derived-model")
    timeseries = get_dataset_by_name(f"LoL gold and stat win-rate timeseries {patch}", "riot-derived-model")
    if not context or not timeseries:
        raise HTTPException(404, f"{patch} 패치의 분석 마트를 먼저 생성하세요.")
    widgets = [
        {"id": f"{patch}-gold", "title": "분당 평균 보유 골드", "type": "line", "column": "total_gold", "dimension": "minute", "aggregation": "mean", "dataset_id": context.id},
        {"id": f"{patch}-ad", "title": "분당 인벤토리 제공 AD", "type": "line", "column": "inventory_ad", "dimension": "minute", "aggregation": "mean", "dataset_id": context.id},
        {"id": f"{patch}-ap", "title": "분당 인벤토리 제공 AP", "type": "line", "column": "inventory_ap", "dimension": "minute", "aggregation": "mean", "dataset_id": context.id},
        {"id": f"{patch}-haste", "title": "분당 인벤토리 제공 스킬 가속", "type": "line", "column": "inventory_ability_haste", "dimension": "minute", "aggregation": "mean", "dataset_id": context.id},
        {"id": f"{patch}-gold-win", "title": "골드 구간별 관찰 승률", "type": "line", "column": "observed_win_rate", "dimension": "gold_bucket_start", "aggregation": "mean", "dataset_id": timeseries.id},
        {"id": f"{patch}-team-diff", "title": "팀 골드 격차와 관찰 승리", "type": "scatter", "column": "team_gold_diff", "secondary": "observed_win", "dataset_id": context.id},
    ]
    return save_or_update_dashboard(f"LoL 분석 시작 대시보드 {patch}", widgets)


@router.post("/api/v1/lol/dashboards/patch-trend", response_model=DashboardSummary, status_code=201)
def create_lol_patch_trend_dashboard() -> DashboardSummary:
    """Create a private dashboard that compares all processed LoL patches."""
    trend = get_dataset_by_name("LoL patch stat trend", "riot-derived-model")
    coverage = get_dataset_by_name("LoL sample coverage", "riot-derived-model")
    if not trend or not coverage:
        raise HTTPException(404, "패치별 경기 마트를 먼저 생성하세요.")
    widgets = [
        {"id": "patch-gold", "title": "패치별 분당 평균 보유 골드", "type": "line", "column": "average_total_gold", "dimension": "minute", "series": "patch", "aggregation": "mean", "dataset_id": trend.id},
        {"id": "patch-ad", "title": "패치별 분당 인벤토리 AD", "type": "line", "column": "average_inventory_ad", "dimension": "minute", "series": "patch", "aggregation": "mean", "dataset_id": trend.id},
        {"id": "patch-ap", "title": "패치별 분당 인벤토리 AP", "type": "line", "column": "average_inventory_ap", "dimension": "minute", "series": "patch", "aggregation": "mean", "dataset_id": trend.id},
        {"id": "patch-ah", "title": "패치별 분당 스킬 가속", "type": "line", "column": "average_inventory_ability_haste", "dimension": "minute", "series": "patch", "aggregation": "mean", "dataset_id": trend.id},
        {"id": "coverage-players", "title": "패치별 시간대 표본 참가자 수", "type": "line", "column": "sample_players", "dimension": "minute", "series": "patch", "aggregation": "sum", "dataset_id": coverage.id},
        {"id": "coverage-inventory", "title": "패치별 인벤토리 결측 비율", "type": "line", "column": "inventory_missing_ratio", "dimension": "minute", "series": "patch", "aggregation": "mean", "dataset_id": coverage.id},
    ]
    return save_or_update_dashboard("LoL 패치 비교·표본 품질 대시보드", widgets)


@router.post("/api/v1/lol/accounts/resolve", response_model=RiotAccountSummary)
async def resolve_riot_account(request: RiotAccountResolveRequest) -> RiotAccountSummary:
    try:
        account = await RiotClient().account_by_riot_id(request.game_name, request.tag_line)
        return RiotAccountSummary(
            puuid=account["puuid"],
            game_name=account.get("gameName", request.game_name),
            tag_line=account.get("tagLine", request.tag_line.lstrip("#")),
        )
    except RiotKeyError as error:
        raise HTTPException(401, str(error)) from error
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise HTTPException(404, "Riot ID를 찾을 수 없습니다.") from error
        raise HTTPException(error.response.status_code, "Riot 계정 조회에 실패했습니다.") from error


@router.post("/api/v1/lol/matches/collect")
async def collect_lol_matches(request: RiotMatchCollectRequest) -> dict:
    try:
        client = RiotClient()
        match_ids = await client.match_ids(request.puuid, count=request.count)
        persisted = []
        for match_id in match_ids:
            directory = settings.root / "bronze" / "riot" / "matches" / match_id
            cached = (directory / "match.json").is_file() and (directory / "timeline.json").is_file()
            paths = await client.persist_match(match_id)
            persisted.append({"match_id": match_id, "cached": cached, "files": [str(path) for path in paths.values()]})
        return {"visibility": "private", "matches": persisted, "fetched": sum(not item["cached"] for item in persisted), "cached": sum(item["cached"] for item in persisted)}
    except RiotKeyError as error:
        raise HTTPException(401, str(error)) from error


@router.post("/api/v1/lol/matches/process")
def process_lol_matches(request: RiotMatchProcessRequest) -> dict:
    try:
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
            result["context_mart"] = sync_named_dataset(mart, f"LoL contextual gold mart {patch_label}", "riot-derived-model")
            result["observed_win_summary"] = sync_named_dataset(build_observed_win_summary(mart), f"LoL observed win cohorts {patch_label}", "riot-derived-model")
            result["gold_win_timeseries"] = sync_named_dataset(build_gold_win_timeseries(mart), f"LoL gold and stat win-rate timeseries {patch_label}", "riot-derived-model")
            result["item_event_mart"] = sync_named_dataset(build_item_event_mart(events, items), f"LoL item completion events {patch_label}", "riot-derived-model")
        return result
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/lol/matches/process-grouped")
async def process_lol_matches_grouped(request: RiotMatchProcessRequest) -> dict:
    """Process a mixed-patch collection with the corresponding item catalog."""
    try:
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
                    dataset for dataset in list_datasets()
                    if dataset.source_type == "riot-data-dragon"
                    and dataset.name.startswith("LoL items ")
                    and patch_key(dataset.name.removeprefix("LoL items ")) == match_patch
                ),
                None,
            )
            if not items:
                synced = await sync_lol_static(LolStaticSyncRequest(version=f"{match_patch}.1"))
                items = synced["items"]
            result = process_lol_matches(RiotMatchProcessRequest(
                match_ids=patch_match_ids,
                snapshot_minutes=request.snapshot_minutes,
                item_dataset_id=items.id,
            ))
            processed[match_patch] = result
            context_frames.append(read_frame(result["context_mart"].id))
        if context_frames:
            trend = sync_named_dataset(
                build_patch_stat_trend(pd.concat(context_frames, ignore_index=True)),
                "LoL patch stat trend",
                "riot-derived-model",
            )
            coverage = sync_named_dataset(
                build_sample_coverage(pd.concat(context_frames, ignore_index=True)),
                "LoL sample coverage",
                "riot-derived-model",
            )
            return {"patches": processed, "patch_stat_trend": trend, "sample_coverage": coverage}
        return {"patches": processed}
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
