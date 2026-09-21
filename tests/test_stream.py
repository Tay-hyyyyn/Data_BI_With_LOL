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


def _write(directory: Path, name: str, records: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(json.dumps(item) for item in records)
    (directory / name).write_text(lines + "\n", "utf-8")


def test_compaction_leaves_the_open_hour_alone_when_a_closed_hour_exists(tmp_path) -> None:
    compactor = load_stream_module("compact")
    bronze = tmp_path / "bronze"
    _write(bronze / "dt=2026-01-01" / "hour=01", "closed.jsonl", [event("old", "2026-01-01T01:00:00Z", 1)])
    _write(bronze / "dt=2026-01-01" / "hour=02", "open.jsonl", [event("new", "2026-01-01T02:10:00Z", 2)])
    destination = tmp_path / "silver"

    assert compactor.compact(bronze, destination, minimum_bytes=999_999_999, now=datetime(2026, 1, 1, 2, 30, tzinfo=UTC))

    manifest = json.loads(next(destination.glob("*.manifest.json")).read_text("utf-8"))
    assert [Path(item).name for item in manifest["source_files"]] == ["closed.jsonl"]


def test_duplicates_across_compaction_runs_do_not_reach_silver_twice(tmp_path) -> None:
    compactor = load_stream_module("compact")
    bronze = tmp_path / "bronze"
    destination = tmp_path / "silver"
    _write(bronze / "dt=2026-01-01" / "hour=01", "first.jsonl", [event("dup", "2026-01-01T01:00:00Z", 1)])
    assert compactor.compact(bronze, destination, minimum_bytes=999_999_999, now=datetime(2026, 1, 1, 2, tzinfo=UTC))

    # A crash replay re-delivers the same event in a later batch that is compacted in a later run.
    _write(bronze / "dt=2026-01-01" / "hour=02", "replay.jsonl", [event("dup", "2026-01-01T01:00:00Z", 1), event("fresh", "2026-01-01T02:00:00Z", 5)])
    assert compactor.compact(bronze, destination, minimum_bytes=999_999_999, now=datetime(2026, 1, 1, 3, tzinfo=UTC))

    paths = [str(path) for path in destination.glob("*.parquet")]
    with duckdb.connect(":memory:") as connection:
        rows = connection.execute("SELECT event_id FROM read_parquet(?, union_by_name=true) ORDER BY event_id", [paths]).fetchall()
    assert rows == [("dup",), ("fresh",)]
