from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from app import storage


def test_publish_exposes_manifest_after_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "settings", SimpleNamespace(root=tmp_path))
    result = storage.publish_dataframe("data", "v1", pd.DataFrame({"x": [1, 2]}))
    manifest = json.loads((tmp_path / "published" / "data" / "v1" / "manifest.json").read_text("utf-8"))
    assert manifest["row_count"] == 2
    assert result["body_sha256"] == manifest["files"][0]["sha256"]
