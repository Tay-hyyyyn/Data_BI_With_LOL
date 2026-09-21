"""Compare pushed-down DuckDB aggregation with the previous load-everything-then-pandas approach.

Usage: python scripts/bench_query.py [rows]
Uses a throwaway data root, so it never touches your real data/ directory.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))
os.environ["DATA_BI_ROOT"] = tempfile.mkdtemp(prefix="bench-")

from app import config, database, storage  # noqa: E402
from app.schemas import DatasetQuery  # noqa: E402
from app.services import bi  # noqa: E402
from app.services.bi import dashboards  # noqa: E402
from app.services.datasets import create_dataset_from_frame, read_frame  # noqa: E402

rows = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000
settings = dataclasses.replace(config.settings, root=Path(os.environ["DATA_BI_ROOT"]))
for module in (database, storage, dashboards):
    module.settings = settings  # type: ignore[attr-defined]
database.initialize_database()

rng = np.random.default_rng(0)
frame = pd.DataFrame(
    {
        "channel": rng.choice(["search", "social", "display", "video", "email"], rows),
        "region": rng.integers(0, 40, rows),
        "spend": rng.random(rows) * 100,
    }
)
dataset_id = create_dataset_from_frame(frame, "bench", "bench").id
request = DatasetQuery(dimension="channel", measure="spend", aggregation="sum")


def measure(label: str, function) -> None:
    tracemalloc.start()
    started = time.perf_counter()
    function()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"{label:<34} {elapsed * 1000:8.0f} ms   peak python heap {peak / 1e6:8.1f} MB")


def previous_approach() -> None:
    loaded = read_frame(dataset_id)
    loaded.groupby("channel", dropna=False)["spend"].sum().reset_index()


print(f"{rows:,} rows")
bi.query_dataset(dataset_id, request)  # warm the parquet metadata / page cache for both paths
measure("pushed down (DuckDB)", lambda: bi.query_dataset(dataset_id, request))
measure("load all + pandas (previous)", previous_approach)
