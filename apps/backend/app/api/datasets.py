from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import settings
from ..schemas import DatasetChartRequest, DatasetChartResult, DatasetDistinctValues, DatasetProfile, DatasetQuery, DatasetQueryResult, DatasetSummary, JobSummary, RelationshipRequest, RelationshipResponse, TransformRequest, TransformResult
from ..services.bi import build_chart, distinct_values, query_dataset
from ..services.datasets import get_profile, ingest_upload, list_datasets, preview
from ..services.jobs import job_runner
from ..services.relationships import analyze_cached
from ..services.transforms import run_recipe


router = APIRouter(tags=["datasets"])


@router.get("/api/v1/datasets", response_model=list[DatasetSummary])
def datasets() -> list[DatasetSummary]:
    return list_datasets()


@router.post("/api/v1/datasets/upload", response_model=DatasetSummary, status_code=201)
async def upload_dataset(file: UploadFile = File(...), name: str | None = Form(None), sheet_name: str | None = Form(None)) -> DatasetSummary:
    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(413, "파일 크기 제한을 초과했습니다.")
    try:
        return ingest_upload(file.filename or "dataset.csv", payload, name, sheet_name)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/api/v1/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def dataset_profile(dataset_id: str) -> DatasetProfile:
    try:
        return get_profile(dataset_id)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error


@router.get("/api/v1/datasets/{dataset_id}/preview")
def dataset_preview(dataset_id: str, limit: int = 100) -> dict:
    try:
        return preview(dataset_id, limit)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error


@router.get("/api/v1/datasets/{dataset_id}/columns/{column}/values", response_model=DatasetDistinctValues)
def dataset_distinct_values(dataset_id: str, column: str, limit: int = 100) -> DatasetDistinctValues:
    try:
        return distinct_values(dataset_id, column, min(max(limit, 1), 500))
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/datasets/{dataset_id}/query", response_model=DatasetQueryResult)
def structured_dataset_query(dataset_id: str, request: DatasetQuery) -> DatasetQueryResult:
    try:
        return query_dataset(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error
    except (TypeError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/datasets/{dataset_id}/chart", response_model=DatasetChartResult)
def dataset_chart(dataset_id: str, request: DatasetChartRequest) -> DatasetChartResult:
    try:
        return build_chart(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error
    except (TypeError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/datasets/{dataset_id}/relationships", response_model=RelationshipResponse)
def relationships(dataset_id: str, request: RelationshipRequest) -> RelationshipResponse:
    try:
        return analyze_cached(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋 또는 컬럼을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/api/v1/datasets/{dataset_id}/relationships/jobs", response_model=JobSummary, status_code=202)
def queue_relationships(dataset_id: str, request: RelationshipRequest) -> JobSummary:
    return job_runner.submit("column_relationships", lambda: analyze_cached(dataset_id, request).model_dump(mode="json"))


@router.post("/api/v1/datasets/{dataset_id}/transform", response_model=TransformResult, status_code=201)
def transform(dataset_id: str, request: TransformRequest) -> TransformResult:
    try:
        return run_recipe(dataset_id, request)
    except KeyError as error:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다.") from error
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error
