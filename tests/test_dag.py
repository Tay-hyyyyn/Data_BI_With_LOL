"""Airflow is not installed in CI, so guard the DAG source directly against the templating bug."""

from __future__ import annotations

from pathlib import Path

DAG = Path(__file__).resolve().parents[1] / "orchestration" / "airflow" / "dags" / "data_bi_active_pipelines.py"


def test_idempotency_key_is_rendered_by_airflow_not_built_in_the_task_body():
    source = DAG.read_text("utf-8")
    # `f"{{{{ ds_nodash }}}}"` inside a TaskFlow body is never rendered by Jinja, so every run reused one key.
    assert "{{{{" not in source
    assert '.partial(' in source and "{{ ts_nodash }}" in source, "key prefix must be a templated task argument"
    assert "ds_nodash" not in source.replace("ts_nodash", ""), "ds_nodash is date-granular; the schedule is hourly"
