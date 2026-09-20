from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.auth import router as auth_router
from .api.bi import router as bi_router
from .api.datasets import router as datasets_router
from .api.lol import router as lol_router
from .api.operations import router as operations_router
from .config import settings
from .database import initialize_database
from .services.jobs import job_runner
from .services.auth import bootstrap_admin, user_from_request
from .services.observability import record_audit


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    bootstrap_admin()
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
app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(operations_router)
app.include_router(lol_router)


def _audit_safely(actor_id: str | None, actor_role: str | None, action: str, resource_path: str, outcome: int) -> None:
    """Keep audit persistence from changing the outcome of a user request."""
    try:
        record_audit(actor_id, actor_role, action, resource_path, outcome)
    except Exception:
        # Audit storage is an observability dependency, not a reason to fail BI work.
        pass


@app.middleware("http")
async def require_authenticated_api(request: Request, call_next):
    path = request.url.path
    public_auth_paths = {"/api/v1/auth/login", "/api/v1/auth/logout"}
    if settings.auth_required and path.startswith("/api/v1/") and path not in public_auth_paths:
        user = user_from_request(request)
        if not user:
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                _audit_safely(None, None, request.method, path, 401)
            return JSONResponse({"detail": "로그인이 필요합니다."}, status_code=401)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and user.role == "viewer":
            _audit_safely(user.id, user.role, request.method, path, 403)
            return JSONResponse({"detail": "조회자 역할은 데이터를 변경할 수 없습니다."}, status_code=403)
        request.state.user = user
    response = await call_next(request)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith("/api/v1/") and path not in public_auth_paths:
        user = getattr(request.state, "user", None)
        _audit_safely(user.id if user else None, user.role if user else None, request.method, path, response.status_code)
    return response


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment,
        "storage_ready": settings.root.exists(),
        "storage_root": str(settings.root),
    }
