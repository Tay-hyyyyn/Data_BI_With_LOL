from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import api_router, health
from .config import settings
from .database import initialize_database
from .errors import register_exception_handlers
from .services.jobs import job_runner
from .storage import cleanup_staging


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    cleanup_staging()  # sweep any staging dirs a previous crash left behind
    job_runner.start()
    yield
    job_runner.stop()


app = FastAPI(title="Data BI With LoL", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(health.router)
app.include_router(api_router)
