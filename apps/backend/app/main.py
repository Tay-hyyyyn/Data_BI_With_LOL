from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.bi import router as bi_router
from .api.datasets import router as datasets_router
from .api.lol import router as lol_router
from .api.operations import router as operations_router
from .config import settings
from .database import initialize_database
from .services.jobs import job_runner


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
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
app.include_router(bi_router)
app.include_router(datasets_router)
app.include_router(operations_router)
app.include_router(lol_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
