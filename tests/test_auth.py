from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import database
from app import main
from app.api import auth as auth_api
from app.schemas import UserWrite
from app.services import auth


def configured_settings(root):
    return SimpleNamespace(
        root=root, auth_required=True, auth_secret="a" * 40,
        admin_email="admin@example.com", admin_password="very-secure-password", auth_cookie_secure=False,
    )


def test_bootstrap_admin_and_signed_session_token(tmp_path, monkeypatch) -> None:
    settings = configured_settings(tmp_path)
    monkeypatch.setattr(database, "settings", settings)
    monkeypatch.setattr(auth, "settings", settings)
    database.initialize_database()
    auth.bootstrap_admin()

    user = auth.authenticate("admin@example.com", "very-secure-password")
    assert user and user.role == "admin"
    assert auth.user_from_token(auth.issue_token(user)).email == "admin@example.com"
    assert auth.authenticate("admin@example.com", "wrong-password") is None


def test_user_password_is_hashed_and_roles_are_preserved(tmp_path, monkeypatch) -> None:
    settings = configured_settings(tmp_path)
    monkeypatch.setattr(database, "settings", settings)
    monkeypatch.setattr(auth, "settings", settings)
    database.initialize_database()
    created = auth.create_user(UserWrite(email="viewer@example.com", password="another-secure-password", role="viewer"))
    assert created.role == "viewer"
    with database.db() as connection:
        stored = connection.execute("SELECT password_hash FROM users WHERE id=?", (created.id,)).fetchone()["password_hash"]
    assert "another-secure-password" not in stored


def test_api_requires_login_and_viewer_cannot_mutate(tmp_path, monkeypatch) -> None:
    settings = configured_settings(tmp_path)
    monkeypatch.setattr(database, "settings", settings)
    monkeypatch.setattr(auth, "settings", settings)
    monkeypatch.setattr(auth_api, "settings", settings)
    monkeypatch.setattr(main, "settings", settings)
    with TestClient(main.app) as client:
        assert client.get("/api/v1/datasets").status_code == 401
        login = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "very-secure-password"})
        assert login.status_code == 200
        viewer = client.post("/api/v1/auth/users", json={"email": "viewer@example.com", "password": "another-secure-password", "role": "viewer"})
        assert viewer.status_code == 201
    with TestClient(main.app) as viewer_client:
        login = viewer_client.post("/api/v1/auth/login", json={"email": "viewer@example.com", "password": "another-secure-password"})
        assert login.status_code == 200
        assert viewer_client.post("/api/v1/dashboards", json={"name": "No write", "widgets": []}).status_code == 403
