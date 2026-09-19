from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb


STREAM = Path(__file__).resolve().parents[1] / "stream"


def load_stream_module(name: str):
    spec = importlib.util.spec_from_file_location(f"stream_{name}", STREAM / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event(event_id: str, event_time: str, amount: int) -> dict:
    return {"event_id": event_id, "domain": "marketing", "dataset": "campaign", "schema_version": "1.0", "event_time": event_time, "payload": {"amount": amount}}


def test_stream_batch_is_atomic_and_idempotent_by_event_set(tmp_path) -> None:
    consumer = load_stream_module("consumer")
    records = [event("b", "2026-01-01T00:00:00Z", 2), event("a", "2026-01-01T00:00:00Z", 1)]

    first = consumer.persist_batch(tmp_path, records)
    second = consumer.persist_batch(tmp_path, list(reversed(records)))

    assert first == second
    assert first.is_file()
    assert json.loads(first.with_suffix(".manifest.json").read_text("utf-8"))["records"] == 2


def test_compaction_deduplicates_events_and_does_not_reprocess_manifested_files(tmp_path) -> None:
    compactor = load_stream_module("compact")
    source = tmp_path / "bronze" / "dt=2026-01-01" / "hour=01"
    source.mkdir(parents=True)
    (source / "batch-a.jsonl").write_text("\n".join(json.dumps(item) for item in [event("same", "2026-01-01T01:00:00Z", 1), event("other", "2026-01-01T01:00:00Z", 2)]) + "\n", "utf-8")
    (source / "batch-b.jsonl").write_text(json.dumps(event("same", "2026-01-01T01:02:00Z", 3)) + "\n", "utf-8")
    destination = tmp_path / "silver"

    assert compactor.compact(tmp_path / "bronze", destination, minimum_bytes=999_999_999, now=datetime(2026, 1, 1, 2, tzinfo=UTC))
    assert not compactor.compact(tmp_path / "bronze", destination, minimum_bytes=1, now=datetime(2026, 1, 1, 2, tzinfo=UTC))
    output = next(destination.glob("*.parquet"))
    with duckdb.connect(":memory:") as connection:
        rows = connection.execute("SELECT event_id, payload.amount FROM read_parquet(?) ORDER BY event_id", [str(output)]).fetchall()
    assert rows == [("other", 2), ("same", 3)]
