from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from app import database
from app.schemas import AnalysisModelWrite, DatasetSummary, ModelJoin
from app.services import models


def test_analysis_model_builds_a_reusable_joined_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    with database.db() as connection:
        for dataset_id in ("base", "channels", "output"):
            connection.execute(
                "INSERT INTO datasets(id,name,source_type,created_at,current_version_id) VALUES(?,?,?,?,?)",
                (dataset_id, dataset_id, "test", "now", None),
            )
    base = pd.DataFrame({"campaign_id": ["a", "b"], "spend": [100, 200]})
    channels = pd.DataFrame({"campaign_key": ["a", "b"], "channel": ["search", "social"]})
    monkeypatch.setattr(models, "get_version", lambda identifier: {"id": f"v-{identifier}"})
    monkeypatch.setattr(models, "read_frame", lambda identifier: base if identifier == "base" else channels)
    captured: dict[str, pd.DataFrame] = {}
    monkeypatch.setattr(models, "sync_named_dataset", lambda frame, name, source_type: captured.update(frame=frame.copy()) or DatasetSummary(id="output", name=name, source_type=source_type, created_at="now", current_version_id="v-output", row_count=len(frame), column_count=len(frame.columns)))

    created = models.create_model(AnalysisModelWrite(
        name="Campaign model", base_dataset_id="base",
        joins=[ModelJoin(dataset_id="channels", left_on=["campaign_id"], right_on=["campaign_key"], how="left", cardinality="one_to_one")],
    ))
    result = models.build_model(created.id)

    assert result == {"model_id": created.id, "dataset_id": "output", "row_count": 2, "status": "published"}
    assert captured["frame"]["channel"].tolist() == ["search", "social"]
    assert models.list_model_runs(created.id)[0].status == "published"
