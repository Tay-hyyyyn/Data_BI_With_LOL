from __future__ import annotations

from fastapi import APIRouter

from ..errors import api_errors, not_found, unprocessable
from ..schemas import JobSummary, PipelineRunRequest, PipelineSummary, PipelineWrite
from ..services.pipelines import create_pipeline, list_pipelines, set_pipeline_enabled
from ..services.pipelines import run_pipeline as run_pipeline_service

router = APIRouter()


@router.get("/pipelines", response_model=list[PipelineSummary])
def pipelines(enabled: bool | None = None) -> list[PipelineSummary]:
    return list_pipelines(enabled)


@router.post("/pipelines", response_model=PipelineSummary, status_code=201)
def register_pipeline(payload: PipelineWrite) -> PipelineSummary:
    with api_errors(not_found("데이터셋을 찾을 수 없습니다.")):
        return create_pipeline(payload)


@router.post("/pipelines/{pipeline_id}/enabled", response_model=PipelineSummary)
def toggle_pipeline(pipeline_id: str, enabled: bool) -> PipelineSummary:
    with api_errors(not_found("파이프라인을 찾을 수 없습니다.")):
        return set_pipeline_enabled(pipeline_id, enabled)


@router.post("/pipelines/{pipeline_id}/run", response_model=JobSummary, status_code=202)
def run_pipeline(pipeline_id: str, request: PipelineRunRequest) -> JobSummary:
    with api_errors(not_found("파이프라인 또는 작업을 찾을 수 없습니다."), unprocessable(ValueError)):
        return run_pipeline_service(pipeline_id, request.idempotency_key)
