from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import settings
from ..errors import api_errors, not_found, unprocessable
from ..schemas import DatasetProfile, DatasetSummary
from ..services.datasets import get_profile, ingest_upload, list_datasets, preview

router = APIRouter()


@router.get("/datasets", response_model=list[DatasetSummary])
def datasets() -> list[DatasetSummary]:
    return list_datasets()


@router.post("/datasets/upload", response_model=DatasetSummary, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    sheet_name: str | None = Form(None),
) -> DatasetSummary:
    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(413, "파일 크기 제한을 초과했습니다.")
    with api_errors(unprocessable(ValueError)):
        return ingest_upload(file.filename or "dataset.csv", payload, name, sheet_name)


@router.get("/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def dataset_profile(dataset_id: str) -> DatasetProfile:
    with api_errors(not_found("데이터셋을 찾을 수 없습니다.")):
        return get_profile(dataset_id)


@router.get("/datasets/{dataset_id}/preview")
def dataset_preview(dataset_id: str, limit: int = 100) -> dict:
    with api_errors(not_found("데이터셋을 찾을 수 없습니다.")):
        return preview(dataset_id, limit)
