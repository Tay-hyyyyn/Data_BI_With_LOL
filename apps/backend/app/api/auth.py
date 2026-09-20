from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..config import settings
from ..schemas import AuthStatus, LoginRequest, UserSummary, UserWrite
from ..services.auth import COOKIE_NAME, authenticate, create_user, issue_token, list_users


router = APIRouter(tags=["auth"])


@router.get("/api/v1/auth/me", response_model=AuthStatus)
def current_user(request: Request) -> AuthStatus:
    if not settings.auth_required:
        return AuthStatus(enabled=False)
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return AuthStatus(enabled=True, user=user)


@router.post("/api/v1/auth/login", response_model=AuthStatus)
def login(payload: LoginRequest, response: Response) -> AuthStatus:
    if not settings.auth_required:
        raise HTTPException(409, "현재 환경에서는 로그인이 비활성화되어 있습니다.")
    user = authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")
    response.set_cookie(COOKIE_NAME, issue_token(user), httponly=True, samesite="lax", secure=settings.auth_cookie_secure, max_age=12 * 60 * 60)
    return AuthStatus(enabled=True, user=user)


@router.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/api/v1/auth/users", response_model=list[UserSummary])
def users(request: Request) -> list[UserSummary]:
    if getattr(request.state, "user", None).role != "admin":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return list_users()


@router.post("/api/v1/auth/users", response_model=UserSummary, status_code=201)
def register_user(payload: UserWrite, request: Request) -> UserSummary:
    if getattr(request.state, "user", None).role != "admin":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    try:
        return create_user(payload)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
