"""Freezes the public HTTP surface. Structural refactors must leave both snapshots byte-identical."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).with_name("openapi.snapshot.json")


def _routes() -> list[list[str]]:
    return sorted(
        [route.path, method]
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    )


def test_route_set_is_stable():
    expected = json.loads(SNAPSHOT.with_name("routes.snapshot.json").read_text("utf-8"))
    assert _routes() == expected


def test_openapi_schema_is_stable():
    expected = json.loads(SNAPSHOT.read_text("utf-8"))
    assert json.loads(json.dumps(app.openapi(), sort_keys=True)) == expected
