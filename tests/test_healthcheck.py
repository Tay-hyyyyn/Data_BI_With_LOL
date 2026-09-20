from __future__ import annotations

import importlib.util
from pathlib import Path


def test_healthcheck_requires_api_and_storage_readiness(monkeypatch) -> None:
    path = Path(__file__).resolve().parents[1] / "scripts" / "healthcheck.py"
    spec = importlib.util.spec_from_file_location("data_bi_healthcheck", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Response:
        def read(self): return b'{"status":"ok","storage_ready":true}'
        def __enter__(self): return self
        def __exit__(self, *_): return None

    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: Response())
    assert module.check("http://localhost:8000") == {"status": "ok", "storage_ready": True}
