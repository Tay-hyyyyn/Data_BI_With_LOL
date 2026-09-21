from __future__ import annotations

from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
