from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import duckdb


def compact(source: Path, destination: Path, minimum_bytes: int = 64 * 1024 * 1024) -> bool:
    files = sorted(source.glob("**/*.jsonl"))
    if not files or sum(path.stat().st_size for path in files) < minimum_bytes:
        return False
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"compact-{files[0].stem}-{files[-1].stem}.parquet"
    temporary = output.with_suffix(".parquet.tmp")
    paths = ",".join("'" + str(path).replace("'", "''") + "'" for path in files)
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            f"COPY (SELECT * EXCLUDE (rn) FROM (SELECT *, row_number() OVER (PARTITION BY event_id ORDER BY event_time DESC) rn FROM read_json_auto([{paths}])) WHERE rn=1) TO '{str(temporary).replace("'", "''")}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"
        )
    os.replace(temporary, output)
    manifest = output.with_suffix(".manifest.json")
    manifest.write_text(json.dumps({"file": output.name, "source_files": [str(path) for path in files]}), "utf-8")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--minimum-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    raise SystemExit(0 if compact(args.source, args.destination, args.minimum_bytes) else 2)
