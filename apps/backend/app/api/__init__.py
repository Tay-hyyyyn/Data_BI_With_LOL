"""HTTP routers. Handlers only parse input, call a service and return; business logic lives in `app.services`."""

from __future__ import annotations

from fastapi import APIRouter

from . import dashboards, datasets, health, jobs, lol, metrics, pipelines, query, relationships, transforms

api_router = APIRouter(prefix="/api/v1")
for module in (datasets, query, relationships, transforms, metrics, dashboards, jobs, pipelines, lol):
    api_router.include_router(module.router)

__all__ = ["api_router", "health"]
