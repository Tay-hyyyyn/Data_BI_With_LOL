from __future__ import annotations

import os
from datetime import datetime

import requests
from airflow.decorators import dag, task

API = os.getenv("DATA_BI_API_URL", "http://host.docker.internal:8000/api/v1")


@dag(
    dag_id="data_bi_active_pipelines",
    start_date=datetime(2026, 1, 1),
    schedule="0 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["data-bi", "optional-lab"],
)
def active_pipelines():
    @task
    def enabled() -> list[dict]:
        response = requests.get(f"{API}/pipelines?enabled=true", timeout=30)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()

    @task(retries=2)
    def run(pipeline: dict, key_prefix: str) -> dict:
        # `key_prefix` arrives already rendered: Airflow only applies Jinja to arguments passed *into* a task,
        # never to strings built inside its body. It is hour-granular (ts_nodash) to match the hourly schedule,
        # and stable across retries so a retried run reuses the same job instead of queuing a duplicate.
        response = requests.post(
            f"{API}/pipelines/{pipeline['id']}/run",
            json={"idempotency_key": f"{key_prefix}-{pipeline['id']}"},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    run.partial(key_prefix="{{ ts_nodash }}").expand(pipeline=enabled())


active_pipelines()
