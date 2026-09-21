from __future__ import annotations

from fastapi import APIRouter

from ..errors import api_errors, not_found, unprocessable
from ..schemas import TransformRequest, TransformResult
from ..services.transforms import run_recipe

router = APIRouter()


@router.post("/datasets/{dataset_id}/transform", response_model=TransformResult, status_code=201)
def transform(dataset_id: str, request: TransformRequest) -> TransformResult:
    with api_errors(not_found("데이터셋을 찾을 수 없습니다."), unprocessable(ValueError, TypeError)):
        return run_recipe(dataset_id, request)
