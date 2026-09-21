"""Freezes the public HTTP surface. Structural refactors must leave both snapshots byte-identical."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).with_name("openapi.snapshot.json")


_FRAMEWORK_ROUTES = {"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}


def _routes() -> list[list[str]]:
    """(path, method) pairs from the OpenAPI schema; `app.routes` is nested in newer FastAPI versions."""
    return sorted(
        [path, method.upper()]
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    )


def test_route_set_is_stable():
    captured = json.loads(SNAPSHOT.with_name("routes.snapshot.json").read_text("utf-8"))
    expected = [entry for entry in captured if entry[0] not in _FRAMEWORK_ROUTES]
    assert _routes() == expected


def test_openapi_schema_is_stable():
    expected = json.loads(SNAPSHOT.read_text("utf-8"))
    assert json.loads(json.dumps(app.openapi(), sort_keys=True)) == expected
