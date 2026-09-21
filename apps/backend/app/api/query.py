from __future__ import annotations

from fastapi import APIRouter

from ..errors import api_errors, not_found, unprocessable
from ..schemas import DatasetChartRequest, DatasetChartResult, DatasetQuery, DatasetQueryResult
from ..services.bi import build_chart, query_dataset

router = APIRouter()


@router.post("/datasets/{dataset_id}/query", response_model=DatasetQueryResult)
def structured_dataset_query(dataset_id: str, request: DatasetQuery) -> DatasetQueryResult:
    with api_errors(not_found("데이터셋을 찾을 수 없습니다."), unprocessable(TypeError, ValueError)):
        return query_dataset(dataset_id, request)


@router.post("/datasets/{dataset_id}/chart", response_model=DatasetChartResult)
def dataset_chart(dataset_id: str, request: DatasetChartRequest) -> DatasetChartResult:
    with api_errors(not_found("데이터셋을 찾을 수 없습니다."), unprocessable(TypeError, ValueError)):
        return build_chart(dataset_id, request)
