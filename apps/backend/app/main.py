from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import initialize_database
from .schemas import DashboardSummary, DashboardWrite, DatasetChartRequest, DatasetChartResult, DatasetProfile, DatasetQuery, DatasetQueryResult, DatasetSummary, JobSummary, LolStaticSyncRequest, MetricSummary, MetricWrite, PipelineRunRequest, PipelineSummary, PipelineWrite, RelationshipRequest, RelationshipResponse, RiotAccountResolveRequest, RiotAccountSummary, RiotMatchCollectRequest, RiotMatchProcessRequest, TransformRequest, TransformResult
from .services.datasets import create_dataset_from_frame, get_profile, ingest_upload, list_datasets, preview, read_frame, sync_named_dataset
from .services.relationships import analyze_cached
from .services.transforms import run_recipe
from .lol.client import RiotClient, RiotKeyError, fetch_data_dragon_bundle
from .lol.benchmark import read_lolps_benchmark_upload
from .lol.items import build_context_mart, build_gold_win_timeseries, build_item_event_mart, build_observed_win_summary, estimate_gold_values, item_efficiency, item_frame, reference_prices
from .lol.static import champion_frame, patch_key, rune_frame
from .lol.timeline import normalize_persisted
from .services.bi import build_chart, clone_dashboard, create_metric, get_dashboard, list_dashboards, query_dataset, save_dashboard, set_dashboard_published, update_dashboard
from .services.jobs import get_job, job_runner, list_jobs
from .services.pipelines import create_pipeline, existing_run_job, get_pipeline, list_pipelines, record_run, set_pipeline_enabled


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    job_runner.start()
    yield
    job_runner.stop()


app = FastAPI(title="Data BI With LoL", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


@app.get("/api/v1/datasets", response_model=list[DatasetSummary])
def datasets() -> list[DatasetSummary]:
    return list_datasets()


@app.post("/api/v1/datasets/upload", response_model=DatasetSummary, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    sheet_name: str | None = Form(None),
) -> DatasetSummary:
    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(413, "파일 크기 제한을 초과했습니다.")
    try:
        return ingest_upload(file.filename or "dataset.csv", payload, name, sheet_name)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/v1/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def dataset_profile(dataset_id: str) -> DatasetProfile:
    try:
        return get_profile(dataset_id)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error


@app.get("/api/v1/datasets/{dataset_id}/preview")
def dataset_preview(dataset_id: str, limit: int = 100) -> dict:
    try:
        return preview(dataset_id, limit)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error


@app.post("/api/v1/datasets/{dataset_id}/query", response_model=DatasetQueryResult)
def structured_dataset_query(dataset_id: str, request: DatasetQuery) -> DatasetQueryResult:
    try:
        return query_dataset(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error
    except (TypeError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/v1/datasets/{dataset_id}/chart", response_model=DatasetChartResult)
def dataset_chart(dataset_id: str, request: DatasetChartRequest) -> DatasetChartResult:
    try:
        return build_chart(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error
    except (TypeError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/v1/datasets/{dataset_id}/relationships", response_model=RelationshipResponse)
def relationships(dataset_id: str, request: RelationshipRequest) -> RelationshipResponse:
    try:
        return analyze_cached(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋 또는 컬럼을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/v1/datasets/{dataset_id}/relationships/jobs", response_model=JobSummary, status_code=202)
def queue_relationships(dataset_id: str, request: RelationshipRequest) -> JobSummary:
    return job_runner.submit(
        "column_relationships",
        lambda: analyze_cached(dataset_id, request).model_dump(mode="json"),
    )


@app.get("/api/v1/jobs", response_model=list[JobSummary])
def jobs(limit: int = 50) -> list[JobSummary]:
    return list_jobs(min(max(limit, 1), 200))


@app.get("/api/v1/jobs/{job_id}", response_model=JobSummary)
def job(job_id: str) -> JobSummary:
    try:
        return get_job(job_id)
    except KeyError as error:
        raise HTTPException(404, "작업을 찾을 수 없습니다.") from error


@app.get("/api/v1/pipelines", response_model=list[PipelineSummary])
def pipelines(enabled: bool | None = None) -> list[PipelineSummary]:
    return list_pipelines(enabled)


@app.post("/api/v1/pipelines", response_model=PipelineSummary, status_code=201)
def register_pipeline(payload: PipelineWrite) -> PipelineSummary:
    try:
        return create_pipeline(payload)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error


@app.post("/api/v1/pipelines/{pipeline_id}/enabled", response_model=PipelineSummary)
def toggle_pipeline(pipeline_id: str, enabled: bool) -> PipelineSummary:
    try:
        return set_pipeline_enabled(pipeline_id, enabled)
    except KeyError as error:
        raise HTTPException(404, "파이프라인을 찾을 수 없습니다.") from error


@app.post("/api/v1/pipelines/{pipeline_id}/run", response_model=JobSummary, status_code=202)
def run_pipeline(pipeline_id: str, request: PipelineRunRequest) -> JobSummary:
    try:
        pipeline = get_pipeline(pipeline_id)
        if not pipeline.enabled:
            raise HTTPException(409, "비활성 파이프라인은 실행할 수 없습니다.")
        previous = existing_run_job(pipeline_id, request.idempotency_key)
        if previous:
            return get_job(previous)
        if pipeline.pipeline_type == "relationships":
            relation_request = RelationshipRequest.model_validate(pipeline.config)
            task = lambda: analyze_cached(pipeline.dataset_id, relation_request).model_dump(mode="json")
        else:
            transform_request = TransformRequest.model_validate(pipeline.config)
            task = lambda: run_recipe(pipeline.dataset_id, transform_request).model_dump(mode="json")
        job = job_runner.submit(f"pipeline:{pipeline.pipeline_type}", task)
        record_run(pipeline_id, request.idempotency_key, job.id)
        return job
    except KeyError as error:
        raise HTTPException(404, "파이프라인 또는 작업을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/v1/datasets/{dataset_id}/transform", response_model=TransformResult, status_code=201)
def transform(dataset_id: str, request: TransformRequest) -> TransformResult:
    try:
        return run_recipe(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/v1/lol/static/sync")
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


@app.post("/api/v1/lol/benchmarks/upload", response_model=DatasetSummary, status_code=201)
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


@app.post("/api/v1/lol/accounts/resolve", response_model=RiotAccountSummary)
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


@app.post("/api/v1/lol/matches/collect")
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


@app.post("/api/v1/lol/matches/process")
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


@app.post("/api/v1/metrics", response_model=MetricSummary, status_code=201)
def define_metric(metric: MetricWrite) -> MetricSummary:
    try:
        return create_metric(metric)
    except (KeyError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/v1/dashboards", response_model=list[DashboardSummary])
def dashboards() -> list[DashboardSummary]:
    return list_dashboards()


@app.get("/api/v1/dashboards/{dashboard_id}", response_model=DashboardSummary)
def dashboard(dashboard_id: str) -> DashboardSummary:
    try:
        return get_dashboard(dashboard_id)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error


@app.post("/api/v1/dashboards", response_model=DashboardSummary, status_code=201)
def create_dashboard(payload: DashboardWrite) -> DashboardSummary:
    return save_dashboard(payload)


@app.put("/api/v1/dashboards/{dashboard_id}", response_model=DashboardSummary)
def edit_dashboard(dashboard_id: str, payload: DashboardWrite) -> DashboardSummary:
    try:
        return update_dashboard(dashboard_id, payload)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error


@app.post("/api/v1/dashboards/{dashboard_id}/clone", response_model=DashboardSummary, status_code=201)
def duplicate_dashboard(dashboard_id: str) -> DashboardSummary:
    try:
        return clone_dashboard(dashboard_id)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error


@app.post("/api/v1/dashboards/{dashboard_id}/publish", response_model=DashboardSummary)
def publish_dashboard(dashboard_id: str, published: bool = True) -> DashboardSummary:
    try:
        return set_dashboard_published(dashboard_id, published)
    except KeyError as error:
        raise HTTPException(404, "대시보드를 찾을 수 없습니다.") from error
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
