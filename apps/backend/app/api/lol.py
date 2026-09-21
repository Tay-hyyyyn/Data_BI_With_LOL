from __future__ import annotations

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import settings
from ..errors import api_errors, unprocessable
from ..lol.client import RiotKeyError
from ..schemas import (
    DashboardSummary,
    DatasetSummary,
    LolStarterDashboardRequest,
    LolStaticSyncRequest,
    RiotAccountResolveRequest,
    RiotAccountSummary,
    RiotMatchCollectRequest,
    RiotMatchProcessRequest,
)
from ..services import lol as lol_service

router = APIRouter(prefix="/lol")

_UNAUTHORIZED = (RiotKeyError, 401, None)
_MISSING_MATCH = (FileNotFoundError, 404, None)


@router.post("/static/sync")
async def sync_lol_static(request: LolStaticSyncRequest) -> dict:
    with api_errors((httpx.HTTPError, 502, None), (ValueError, 502, None)):
        return await lol_service.sync_static(request)


@router.post("/benchmarks/upload", response_model=DatasetSummary, status_code=201)
async def upload_lolps_benchmark(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    sheet_name: str | None = Form(None),
) -> DatasetSummary:
    payload = await file.read(settings.max_upload_bytes + 1)
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(413, "파일 크기 제한을 초과했습니다.")
    with api_errors(unprocessable(ValueError)):
        return lol_service.import_benchmark(file.filename or "lolps-benchmark.csv", payload, name, sheet_name)


@router.post("/dashboards/starter", response_model=DashboardSummary, status_code=201)
def create_lol_starter_dashboard(request: LolStarterDashboardRequest) -> DashboardSummary:
    return lol_service.create_starter_dashboard(request)


@router.post("/dashboards/patch-trend", response_model=DashboardSummary, status_code=201)
def create_lol_patch_trend_dashboard() -> DashboardSummary:
    """Create a private dashboard that compares all processed LoL patches."""
    return lol_service.create_patch_trend_dashboard()


@router.post("/accounts/resolve", response_model=RiotAccountSummary)
async def resolve_riot_account(request: RiotAccountResolveRequest) -> RiotAccountSummary:
    with api_errors(_UNAUTHORIZED):
        return await lol_service.resolve_account(request)


@router.post("/matches/collect")
async def collect_lol_matches(request: RiotMatchCollectRequest) -> dict:
    with api_errors(_UNAUTHORIZED):
        return await lol_service.collect_matches(request)


@router.post("/matches/process")
def process_lol_matches(request: RiotMatchProcessRequest) -> dict:
    with api_errors(_MISSING_MATCH, unprocessable(ValueError)):
        return lol_service.process_matches(request)


@router.post("/matches/process-grouped")
async def process_lol_matches_grouped(request: RiotMatchProcessRequest) -> dict:
    """Process a mixed-patch collection safely rather than applying one item catalog to all games."""
    with api_errors(_MISSING_MATCH, unprocessable(ValueError)):
        return await lol_service.process_matches_grouped(request)
