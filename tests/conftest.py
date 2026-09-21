from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

# `settings` is imported by value into these modules, so every one must be patched together.
SETTINGS_HOLDERS = ("app.database", "app.storage", "app.services.bi.dashboards", "app.lol.client", "app.services.lol")


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    import importlib

    from app.config import settings

    patched = dataclasses.replace(settings, root=tmp_path)
    for name in SETTINGS_HOLDERS:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        if hasattr(module, "settings"):
            monkeypatch.setattr(module, "settings", patched)
    return tmp_path


@pytest.fixture
def client(data_root):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_csv() -> bytes:
    return (ROOT / "samples" / "marketing_campaigns.csv").read_bytes()


@pytest.fixture
def dataset(client, sample_csv) -> dict:
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("marketing.csv", sample_csv, "text/csv")},
        data={"name": "marketing"},
    )
    assert response.status_code == 201, response.text
    return response.json()
