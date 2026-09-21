from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from app import database
from app.schemas import MetricWrite
from app.services import bi
from app.services.bi import metrics as bi_metrics


def test_metrics_can_be_updated_and_recomputed_from_current_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    with database.db() as connection:
        connection.execute("INSERT INTO datasets(id,name,source_type,created_at,current_version_id) VALUES(?,?,?,?,?)", ("marketing", "Marketing", "upload", "2026-01-01", "v1"))
    frame = pd.DataFrame({"revenue": [100.0, 200.0], "spend": [50.0, 100.0]})
    monkeypatch.setattr(bi_metrics, "read_frame", lambda _: frame)

    created = bi.create_metric(MetricWrite(name="ROAS", dataset_id="marketing", aggregation="ratio", numerator="revenue", denominator="spend", unit="x"))
    updated = bi.create_metric(MetricWrite(name="ROAS", dataset_id="marketing", aggregation="mean", column="revenue", unit="KRW"))

    assert created.value == 2.0
    assert updated.value == 150.0
    metrics = bi.list_metrics("marketing")
    assert len(metrics) == 1
    assert metrics[0].unit == "KRW"
    assert metrics[0].value == 150.0
