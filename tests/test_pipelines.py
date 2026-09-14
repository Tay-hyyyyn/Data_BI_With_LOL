from __future__ import annotations

from types import SimpleNamespace

from app import database
from app.schemas import PipelineWrite
from app.services import pipelines


def test_pipeline_registry_filters_enabled_entries(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    with database.db() as connection:
        connection.execute(
            "INSERT INTO datasets(id,name,source_type,created_at,current_version_id) VALUES(?,?,?,?,?)",
            ("dataset-1", "Sample", "upload", "2026-01-01T00:00:00Z", None),
        )

    created = pipelines.create_pipeline(
        PipelineWrite(
            name="Relationship refresh",
            dataset_id="dataset-1",
            pipeline_type="relationships",
            config={"column": "spend"},
            enabled=True,
        )
    )

    assert created.enabled
    assert [item.id for item in pipelines.list_pipelines(enabled=True)] == [created.id]
    assert pipelines.list_pipelines(enabled=False) == []
