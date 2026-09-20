from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from app import database
from app.schemas import DataSourceWrite
from app.services import sources
from app.services.datasets import read_frame


def test_sqlite_demo_source_syncs_to_a_versioned_bi_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    source = sources.create_source(DataSourceWrite(
        name="Demo orders", source_type="sqlite_demo", table_name="orders",
        primary_key="order_id", watermark_column="updated_at",
    ))

    first = sources.sync_source(source.id, "full")
    assert first["status"] == "published"
    assert first["synced_rows"] == 240
    assert len(read_frame(first["dataset_id"])) == 240
    assert sources.source_status(source.id)["quality_history"][0]["row_count"] == 240

    second = sources.sync_source(source.id, "incremental")
    assert second["status"] == "unchanged"
    assert second["synced_rows"] == 0


def test_postgres_source_never_persists_a_connection_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    source = sources.create_source(DataSourceWrite(
        name="External reporting", source_type="postgresql", table_name="daily_sales",
        primary_key="id", watermark_column="updated_at", connection_env_var="REPORTING_DATABASE_URL",
    ))
    assert source.connection_env_var == "REPORTING_DATABASE_URL"
    with database.db() as connection:
        stored = connection.execute("SELECT connection_env_var, config_json FROM data_sources WHERE id=?", (source.id,)).fetchone()
    assert stored["connection_env_var"] == "REPORTING_DATABASE_URL"
    assert "postgres" not in stored["config_json"].lower()


def test_schema_drift_blocks_publish_until_explicitly_accepted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    source = sources.create_source(DataSourceWrite(
        name="Schema guarded", source_type="sqlite_demo", table_name="orders",
        primary_key="order_id", watermark_column="updated_at",
    ))
    sources.sync_source(source.id, "full")
    with sqlite3.connect(sources.ensure_demo_database()) as connection:
        connection.execute("ALTER TABLE orders ADD COLUMN campaign TEXT")

    with pytest.raises(ValueError, match="스키마"):
        sources.sync_source(source.id, "full")
    assert sources.list_sync_events(source.id)[0].status == "schema_changed"

    accepted = sources.sync_source(source.id, "full", accept_schema_change=True)
    assert accepted["status"] == "published"
