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
    def run(pipeline: dict) -> dict:
        response = requests.post(
            f"{API}/pipelines/{pipeline['id']}/run",
            json={"idempotency_key": f"{{{{ ds_nodash }}}}-{pipeline['id']}"},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    run.expand(pipeline=enabled())

    @task
    def enabled_sources() -> list[dict]:
        response = requests.get(f"{API}/sources?enabled=true", timeout=30)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()

    @task(retries=2)
    def sync_source(source: dict) -> dict:
        response = requests.post(
            f"{API}/sources/{source['id']}/sync",
            json={"idempotency_key": f"{{{{ ds_nodash }}}}-{source['id']}", "mode": "incremental"},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    sync_source.expand(source=enabled_sources())


active_pipelines()
