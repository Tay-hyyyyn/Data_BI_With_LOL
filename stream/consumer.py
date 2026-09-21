from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

REQUIRED = {"event_id", "domain", "dataset", "schema_version", "event_time", "payload"}


def validate_event(record: dict) -> None:
    missing = REQUIRED - record.keys()
    if missing:
        raise ValueError(f"필수 이벤트 필드 누락: {', '.join(sorted(missing))}")
    major = str(record["schema_version"]).split(".", 1)[0]
    if major != "1":
        raise ValueError(f"지원하지 않는 schema major version: {record['schema_version']}")


def persist_batch(root: Path, records: list[dict]) -> Path:
    for record in records:
        validate_event(record)
    batch_id = hashlib.sha256("\n".join(sorted(str(record["event_id"]) for record in records)).encode()).hexdigest()[:20]
    directory = root / "bronze" / "stream" / datetime.now(UTC).strftime("dt=%Y-%m-%d/hour=%H")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"batch-{batch_id}.jsonl"
    if target.exists():
        return target
    temporary = target.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    manifest = target.with_suffix(".manifest.json")
    manifest_temp = manifest.with_suffix(".json.tmp")
    manifest_temp.write_text(json.dumps({"batch_id": batch_id, "records": len(records), "file": target.name}), "utf-8")
    os.replace(manifest_temp, manifest)
    return target


def run(broker: str, topic: str, root: Path, batch_size: int, flush_seconds: float) -> None:
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        topic, bootstrap_servers=broker, group_id="data-bi-bronze-v1",
        enable_auto_commit=False, auto_offset_reset="earliest",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    batch: list[dict] = []
    started_at = time.monotonic()
    while True:
        messages = consumer.poll(timeout_ms=1_000, max_records=batch_size)
        for records in messages.values():
            batch.extend(message.value for message in records)
        if batch and (len(batch) >= batch_size or time.monotonic() - started_at >= flush_seconds):
            persist_batch(root, batch)
            consumer.commit()  # manifest 확정 후에만 offset 확정
            batch.clear()
            started_at = time.monotonic()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker", default="localhost:19092")
    parser.add_argument("--topic", default="data-bi-events")
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--flush-seconds", type=float, default=10.0)
    args = parser.parse_args()
    run(args.broker, args.topic, args.root, args.batch_size, args.flush_seconds)
