from __future__ import annotations

from fastapi import APIRouter

from ..errors import api_errors, not_found
from ..schemas import JobSummary
from ..services.jobs import get_job, list_jobs

router = APIRouter()


@router.get("/jobs", response_model=list[JobSummary])
def jobs(limit: int = 50) -> list[JobSummary]:
    return list_jobs(min(max(limit, 1), 200))


@router.get("/jobs/{job_id}", response_model=JobSummary)
def job(job_id: str) -> JobSummary:
    with api_errors(not_found("작업을 찾을 수 없습니다.")):
        return get_job(job_id)
