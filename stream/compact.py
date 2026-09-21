from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import duckdb


def _quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _quoted_list(paths: list[Path]) -> str:
    return ",".join(_quote(path) for path in paths)


def compact(source: Path, destination: Path, minimum_bytes: int = 64 * 1024 * 1024, now: datetime | None = None) -> bool:
    destination.mkdir(parents=True, exist_ok=True)
    processed = {
        item
        for manifest in destination.glob("*.manifest.json")
        for item in json.loads(manifest.read_text("utf-8")).get("source_files", [])
    }
    files = sorted(path for path in source.glob("**/*.jsonl") if str(path) not in processed)
    if not files:
        return False
    current_hour = (now or datetime.now(UTC)).strftime("dt=%Y-%m-%d/hour=%H")
    closed = [path for path in files if current_hour not in path.as_posix()]
    # The open hour is still being written, so it is only compacted once it is large enough on its own.
    # Mixing it into a run because *some other* hour closed would split one hour across several outputs.
    selected = files if sum(path.stat().st_size for path in files) >= minimum_bytes else closed
    if not selected:
        return False
    files = selected
    source_key = "\n".join(f"{path}:{path.stat().st_size}" for path in files)
    output = destination / f"compact-{hashlib.sha256(source_key.encode()).hexdigest()[:20]}.parquet"
    temporary = output.with_suffix(".parquet.tmp")
    paths = _quoted_list(files)
    # Bronze can hold the same event_id in different files (a crash replay re-batches events), and those files
    # may be compacted in different runs. Skip events already present in earlier Silver output.
    existing = sorted(destination.glob("compact-*.parquet"))
    already_seen = f" AND event_id NOT IN (SELECT event_id FROM read_parquet([{_quoted_list(existing)}], union_by_name=true))" if existing else ""  # noqa: S608 - every path goes through _quote
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            f"COPY (SELECT * EXCLUDE (rn) FROM (SELECT *, row_number() OVER (PARTITION BY event_id ORDER BY event_time DESC) rn FROM read_json_auto([{paths}], union_by_name=true)) WHERE rn=1{already_seen}) TO {_quote(temporary)} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"  # noqa: S608 - every path goes through _quote
        )
    os.replace(temporary, output)
    manifest = output.with_suffix(".manifest.json")
    manifest_temp = manifest.with_suffix(".json.tmp")
    manifest_temp.write_text(json.dumps({"file": output.name, "source_files": [str(path) for path in files]}), "utf-8")
    os.replace(manifest_temp, manifest)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--minimum-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    raise SystemExit(0 if compact(args.source, args.destination, args.minimum_bytes) else 2)
