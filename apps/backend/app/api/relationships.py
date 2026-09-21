from __future__ import annotations

from fastapi import APIRouter

from ..errors import api_errors, not_found, unprocessable
from ..schemas import JobSummary, RelationshipRequest, RelationshipResponse
from ..services.jobs import job_runner
from ..services.relationships import analyze_cached

router = APIRouter()


@router.post("/datasets/{dataset_id}/relationships", response_model=RelationshipResponse)
def relationships(dataset_id: str, request: RelationshipRequest) -> RelationshipResponse:
    with api_errors(not_found("데이터셋 또는 컬럼을 찾을 수 없습니다."), unprocessable(ValueError)):
        return analyze_cached(dataset_id, request)


@router.post("/datasets/{dataset_id}/relationships/jobs", response_model=JobSummary, status_code=202)
def queue_relationships(dataset_id: str, request: RelationshipRequest) -> JobSummary:
    return job_runner.submit(
        "column_relationships",
        lambda: analyze_cached(dataset_id, request).model_dump(mode="json"),
    )
