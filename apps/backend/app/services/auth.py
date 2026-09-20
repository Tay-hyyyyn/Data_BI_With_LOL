from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request

from ..config import settings
from ..database import db
from ..schemas import UserSummary, UserWrite
from .datasets import utcnow


COOKIE_NAME = "data_bi_session"
TOKEN_TTL_HOURS = 12


def _b64(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _unb64(payload: str) -> bytes:
    return base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    value = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_b64(salt)}${_b64(value)}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$", 2)
        return hmac.compare_digest(_password_hash(password, _unb64(salt)), stored)
    except (TypeError, ValueError):
        return False


def _from_row(row) -> UserSummary:
    return UserSummary(id=row["id"], email=row["email"], role=row["role"], created_at=row["created_at"])


def validate_auth_config() -> None:
    if not settings.auth_required:
        return
    if len(settings.auth_secret) < 32:
        raise RuntimeError("배포 인증에는 32자 이상의 DATA_BI_AUTH_SECRET이 필요합니다.")
    if not settings.admin_email or not settings.admin_password or len(settings.admin_password) < 12:
        raise RuntimeError("배포 인증에는 DATA_BI_ADMIN_EMAIL과 12자 이상 DATA_BI_ADMIN_PASSWORD가 필요합니다.")


def bootstrap_admin() -> None:
    validate_auth_config()
    if not settings.auth_required:
        return
    with db() as connection:
        existing = connection.execute("SELECT id FROM users WHERE email=?", (settings.admin_email.lower(),)).fetchone()
        if not existing:
            now = utcnow()
            connection.execute(
                "INSERT INTO users(id,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (uuid.uuid4().hex, settings.admin_email.lower(), _password_hash(settings.admin_password), "admin", now, now),
            )


def list_users() -> list[UserSummary]:
    with db() as connection:
        rows = connection.execute("SELECT id,email,role,created_at FROM users ORDER BY created_at").fetchall()
    return [_from_row(row) for row in rows]


def create_user(payload: UserWrite) -> UserSummary:
    email, now = payload.email.strip().lower(), utcnow()
    with db() as connection:
        try:
            connection.execute(
                "INSERT INTO users(id,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (uuid.uuid4().hex, email, _password_hash(payload.password), payload.role, now, now),
            )
            row = connection.execute("SELECT id,email,role,created_at FROM users WHERE email=?", (email,)).fetchone()
        except Exception as error:
            if "UNIQUE" in str(error).upper():
                raise ValueError("이미 등록된 이메일입니다.") from error
            raise
    return _from_row(row)


def authenticate(email: str, password: str) -> UserSummary | None:
    with db() as connection:
        row = connection.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        return None
    return _from_row(row)


def issue_token(user: UserSummary) -> str:
    payload = {"sub": user.id, "role": user.role, "exp": int((datetime.now(UTC) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()), "nonce": secrets.token_hex(8)}
    encoded = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def user_from_token(token: str | None) -> UserSummary | None:
    if not token or not settings.auth_secret:
        return None
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64(hmac.new(settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_unb64(encoded))
        if int(payload["exp"]) < int(datetime.now(UTC).timestamp()):
            return None
        with db() as connection:
            row = connection.execute("SELECT id,email,role,created_at FROM users WHERE id=?", (payload["sub"],)).fetchone()
        return _from_row(row) if row else None
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def user_from_request(request: Request) -> UserSummary | None:
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else request.cookies.get(COOKIE_NAME)
    return user_from_token(token)
