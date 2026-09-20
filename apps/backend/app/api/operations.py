from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import JobSummary, PipelineRunRequest, PipelineSummary, PipelineWrite, RelationshipRequest, TransformRequest
from ..services.jobs import get_job, job_runner, list_jobs
from ..services.pipelines import create_pipeline, existing_run_job, get_pipeline, list_pipelines, record_run, set_pipeline_enabled
from ..services.relationships import analyze_cached
from ..services.transforms import run_recipe


router = APIRouter(tags=["operations"])


@router.get("/api/v1/jobs", response_model=list[JobSummary])
def jobs(limit: int = 50) -> list[JobSummary]:
    return list_jobs(min(max(limit, 1), 200))


@router.get("/api/v1/jobs/{job_id}", response_model=JobSummary)
def job(job_id: str) -> JobSummary:
    try:
        return get_job(job_id)
    except KeyError as error:
        raise HTTPException(404, "작업을 찾을 수 없습니다.") from error


@router.get("/api/v1/pipelines", response_model=list[PipelineSummary])
def pipelines(enabled: bool | None = None) -> list[PipelineSummary]:
    return list_pipelines(enabled)


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
