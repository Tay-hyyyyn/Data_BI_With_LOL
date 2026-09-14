from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    current_version_id TEXT,
    visibility TEXT NOT NULL DEFAULT 'private'
);
CREATE TABLE IF NOT EXISTS dataset_versions (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    column_count INTEGER NOT NULL,
    schema_json TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(dataset_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_versions_dataset_created
ON dataset_versions(dataset_id, created_at DESC);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_updated ON jobs(status, updated_at DESC);
CREATE TABLE IF NOT EXISTS relationship_cache (
    cache_key TEXT PRIMARY KEY,
    dataset_version_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    accessed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_relationship_cache_expiry ON relationship_cache(expires_at);
CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    unit TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(dataset_id, name)
);
CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    pipeline_type TEXT NOT NULL,
    config_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pipelines_enabled ON pipelines(enabled, updated_at DESC);
CREATE TABLE IF NOT EXISTS pipeline_runs (
    pipeline_id TEXT NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(pipeline_id, idempotency_key)
);
"""


def initialize_database() -> None:
    settings.root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.root / "metadata.db", timeout=5) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.executescript(SCHEMA)
        connection.execute("PRAGMA optimize")


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(settings.root / "metadata.db", timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
