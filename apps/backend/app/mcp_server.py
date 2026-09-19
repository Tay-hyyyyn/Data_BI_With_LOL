from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP


mcp = FastMCP("Data-BI-With-LoL")
BASE_URL = os.getenv("DATA_BI_API_URL", "http://127.0.0.1:8000/api/v1")


def _get(path: str) -> Any:
    response = httpx.get(f"{BASE_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def _post(path: str, payload: dict[str, Any]) -> Any:
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


@mcp.tool()
def list_datasets() -> dict[str, Any]:
    """사용 가능한 데이터셋과 현재 버전을 반환합니다."""
    return {"datasets": _get("/datasets")}


@mcp.tool()
def describe_dataset(dataset_id: str) -> dict[str, Any]:
    """데이터셋의 컬럼 유형, 결측률, 고유값 수를 반환합니다."""
    return _get(f"/datasets/{dataset_id}/profile")


@mcp.tool()
def preview_dataset(dataset_id: str, limit: int = 20) -> dict[str, Any]:
    """게시된 데이터셋을 최대 100행까지 구조화된 JSON으로 미리 봅니다."""
    return _get(f"/datasets/{dataset_id}/preview?limit={min(max(limit, 1), 100)}")


@mcp.tool()
def query_dataset(
    dataset_id: str,
    measure: str,
    aggregation: str = "sum",
    dimension: str | None = None,
    series: str | None = None,
    filter_column: str | None = None,
    filter_value: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """임의 SQL 없이 게시 버전에 집계·그룹·선택 계열·동등 필터를 적용합니다."""
    filters = []
    if filter_column and filter_value is not None:
        filters.append({"column": filter_column, "operator": "eq", "value": filter_value})
    return _post(
        f"/datasets/{dataset_id}/query",
        {
            "measure": measure,
            "aggregation": aggregation,
            "dimension": dimension,
            "series": series,
            "filters": filters,
            "limit": min(max(limit, 1), 1_000),
        },
    )


@mcp.tool()
def analyze_column_relationships(
    dataset_id: str,
    column: str,
    limit: int = 5,
    entity_key: str | None = None,
    time_column: str | None = None,
    analysis_grain: str | None = None,
) -> dict[str, Any]:
    """선택한 컬럼과 통계적 관계를 반환하며 반복측정 데이터는 entity/time/grain으로 정리할 수 있습니다."""
    return _post(f"/datasets/{dataset_id}/relationships", {
        "column": column, "result_limit": limit, "entity_key": entity_key,
        "time_column": time_column, "analysis_grain": analysis_grain,
    })


@mcp.tool()
def generate_chart_spec(dataset_id: str, column: str) -> dict[str, Any]:
    """선택 컬럼의 최상위 관계와 안전한 ECharts 차트 초안을 반환합니다."""
    result = _post(f"/datasets/{dataset_id}/relationships", {"column": column, "result_limit": 1})
    return {"selected_column": column, "recommendation": result["items"][0] if result["items"] else None}


@mcp.tool()
def get_job_status(job_id: str) -> dict[str, Any]:
    """비동기 분석·수집 작업의 진행률과 결과를 반환합니다."""
    return _get(f"/jobs/{job_id}")


if __name__ == "__main__":
    mcp.run()
