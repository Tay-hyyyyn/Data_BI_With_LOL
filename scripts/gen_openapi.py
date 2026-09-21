"""Dump the FastAPI OpenAPI schema without starting a server (feeds frontend type generation)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from app.main import app  # noqa: E402

target = ROOT / "apps" / "frontend" / "openapi.json"
target.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {target.relative_to(ROOT)}")
