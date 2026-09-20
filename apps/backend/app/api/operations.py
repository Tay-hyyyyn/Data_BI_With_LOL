from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import db
from ..schemas import AnalysisModelRun, AnalysisModelSummary, AnalysisModelWrite, DataSourceSummary, DataSourceWrite, JobSummary, PipelineRunRequest, PipelineSummary, PipelineWrite, RelationshipRequest, SourceSyncEvent, SourceSyncRequest, TransformRequest
from ..services.jobs import get_job, job_runner, list_jobs
from ..services.pipelines import create_pipeline, existing_run_job, get_pipeline, list_pipelines, record_run, set_pipeline_enabled
from ..services.relationships import analyze_cached
from ..services.transforms import run_recipe
from ..services.sources import create_source, get_source, list_sources, list_sync_events, set_source_enabled, source_status, sync_source_with_retry
from ..services.models import build_model, create_model, get_model, list_model_runs, list_models
from ..services.observability import list_alerts, list_audit_events


router = APIRouter(tags=["operations"])


@router.get("/api/v1/jobs", response_model=list[JobSummary])
def jobs(limit: int = 50) -> list[JobSummary]:
    return list_jobs(min(max(limit, 1), 200))


@router.get("/api/v1/operations/alerts")
def alerts(limit: int = 50) -> list[dict]:
    return list_alerts(limit)


@router.get("/api/v1/operations/audit")
def audit_events(limit: int = 50) -> list[dict]:
    return list_audit_events(limit)


@router.get("/api/v1/jobs/{job_id}", response_model=JobSummary)
def job(job_id: str) -> JobSummary:
    try:
        return get_job(job_id)
    except KeyError as error:
        raise HTTPException(404, "작업을 찾을 수 없습니다.") from error


@router.get("/api/v1/pipelines", response_model=list[PipelineSummary])
def pipelines(enabled: bool | None = None) -> list[PipelineSummary]:
    return list_pipelines(enabled)


@router.get("/api/v1/sources", response_model=list[DataSourceSummary])
def sources(enabled: bool | None = None) -> list[DataSourceSummary]:
    return list_sources(enabled)


@router.post("/api/v1/sources", response_model=DataSourceSummary, status_code=201)
def register_source(payload: DataSourceWrite) -> DataSourceSummary:
    try:
        return create_source(payload)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/sources/{source_id}/enabled", response_model=DataSourceSummary)
def toggle_source(source_id: str, enabled: bool) -> DataSourceSummary:
    try:
        return set_source_enabled(source_id, enabled)
    except KeyError as error:
        raise HTTPException(404, "데이터 소스를 찾을 수 없습니다.") from error


@router.get("/api/v1/sources/{source_id}/status")
def get_source_status(source_id: str) -> dict:
    try:
        return source_status(source_id)
    except KeyError as error:
        raise HTTPException(404, "데이터 소스를 찾을 수 없습니다.") from error


@router.get("/api/v1/sources/{source_id}/events", response_model=list[SourceSyncEvent])
def source_events(source_id: str, limit: int = 20) -> list[SourceSyncEvent]:
    try:
        get_source(source_id)
        return list_sync_events(source_id, limit)
    except KeyError as error:
        raise HTTPException(404, "데이터 소스를 찾을 수 없습니다.") from error


@router.get("/api/v1/models", response_model=list[AnalysisModelSummary])
def models() -> list[AnalysisModelSummary]:
    return list_models()


@router.post("/api/v1/models", response_model=AnalysisModelSummary, status_code=201)
def register_model(payload: AnalysisModelWrite) -> AnalysisModelSummary:
    try:
        return create_model(payload)
    except KeyError as error:
        raise HTTPException(404, "분석 모델의 데이터셋을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/api/v1/models/{model_id}/runs", response_model=list[AnalysisModelRun])
def model_runs(model_id: str, limit: int = 20) -> list[AnalysisModelRun]:
    try:
        return list_model_runs(model_id, limit)
    except KeyError as error:
        raise HTTPException(404, "분석 모델을 찾을 수 없습니다.") from error


@router.post("/api/v1/models/{model_id}/build", response_model=JobSummary, status_code=202)
def queue_model_build(model_id: str) -> JobSummary:
    try:
        get_model(model_id)
        return job_runner.submit("analysis_model_build", lambda: build_model(model_id))
    except KeyError as error:
        raise HTTPException(404, "분석 모델을 찾을 수 없습니다.") from error


@router.post("/api/v1/sources/{source_id}/sync", response_model=JobSummary, status_code=202)
def queue_source_sync(source_id: str, request: SourceSyncRequest) -> JobSummary:
    try:
        source = get_source(source_id)
        with db() as connection:
            previous = connection.execute(
                "SELECT job_id FROM source_sync_runs WHERE source_id=? AND idempotency_key=?",
                (source_id, request.idempotency_key),
            ).fetchone()
        if previous:
            return get_job(previous["job_id"])
        if not source.enabled:
            raise HTTPException(409, "비활성 데이터 소스는 동기화할 수 없습니다.")
        job = job_runner.submit("source_sync", lambda: sync_source_with_retry(source_id, request.mode, request.accept_schema_change))
        with db() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO source_sync_runs(source_id,idempotency_key,job_id,created_at) VALUES(?,?,?,datetime('now'))",
                (source_id, request.idempotency_key, job.id),
            )
        return job
    except KeyError as error:
        raise HTTPException(404, "데이터 소스를 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/pipelines", response_model=PipelineSummary, status_code=201)
def register_pipeline(payload: PipelineWrite) -> PipelineSummary:
    try:
        return create_pipeline(payload)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error


@router.post("/api/v1/pipelines/{pipeline_id}/enabled", response_model=PipelineSummary)
def toggle_pipeline(pipeline_id: str, enabled: bool) -> PipelineSummary:
    try:
        return set_pipeline_enabled(pipeline_id, enabled)
    except KeyError as error:
        raise HTTPException(404, "파이프라인을 찾을 수 없습니다.") from error


@router.post("/api/v1/pipelines/{pipeline_id}/run", response_model=JobSummary, status_code=202)
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
