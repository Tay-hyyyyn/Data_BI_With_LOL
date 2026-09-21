"""One HTTP-level test per router so structural moves have a safety net."""

from __future__ import annotations


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_upload_profile_preview(client, dataset):
    dataset_id = dataset["id"]
    assert dataset["row_count"] > 0
    assert any(item["id"] == dataset_id for item in client.get("/api/v1/datasets").json())
    profile = client.get(f"/api/v1/datasets/{dataset_id}/profile").json()
    assert profile["dataset_id"] == dataset_id and profile["columns"]
    preview = client.get(f"/api/v1/datasets/{dataset_id}/preview", params={"limit": 5}).json()
    assert len(preview["rows"]) == 5


def test_upload_rejects_unsupported_file(client):
    response = client.post("/api/v1/datasets/upload", files={"file": ("x.txt", b"hello", "text/plain")})
    assert response.status_code == 422


def test_unknown_dataset_is_404(client):
    assert client.get("/api/v1/datasets/nope/profile").status_code == 404


def test_query_and_chart(client, dataset):
    dataset_id = dataset["id"]
    query = client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        json={"dimension": "channel", "measure": "revenue", "aggregation": "sum"},
    )
    assert query.status_code == 200 and query.json()["rows"]
    bad = client.post(f"/api/v1/datasets/{dataset_id}/query", json={"dimension": "missing"})
    assert bad.status_code == 422
    chart = client.post(f"/api/v1/datasets/{dataset_id}/chart", json={"chart_type": "histogram", "x": "spend"})
    assert chart.status_code == 200 and chart.json()["chart_spec"]


def test_relationships_sync_and_job(client, dataset):
    dataset_id = dataset["id"]
    sync = client.post(f"/api/v1/datasets/{dataset_id}/relationships", json={"column": "revenue"})
    assert sync.status_code == 200 and sync.json()["items"]
    queued = client.post(f"/api/v1/datasets/{dataset_id}/relationships/jobs", json={"column": "revenue"})
    assert queued.status_code == 202
    assert client.get(f"/api/v1/jobs/{queued.json()['id']}").status_code == 200
    assert isinstance(client.get("/api/v1/jobs").json(), list)
    assert client.get("/api/v1/jobs/nope").status_code == 404


def test_transform_publishes_new_version(client, dataset):
    dataset_id = dataset["id"]
    response = client.post(
        f"/api/v1/datasets/{dataset_id}/transform",
        json={"name": "slim", "steps": [{"operation": "select", "config": {"columns": ["channel", "revenue"]}}]},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["version_number"] == 2 and body["column_count"] == 2


def test_metrics_roundtrip(client, dataset):
    payload = {"name": "총 매출", "dataset_id": dataset["id"], "aggregation": "sum", "column": "revenue"}
    created = client.post("/api/v1/metrics", json=payload)
    assert created.status_code in (200, 201), created.text
    assert any(item["name"] == "총 매출" for item in client.get("/api/v1/metrics").json())


def test_dashboard_lifecycle(client, dataset):
    widget = {"id": "w1", "type": "bar", "dataset_id": dataset["id"], "dimension": "channel", "measure": "revenue", "aggregation": "sum"}
    created = client.post("/api/v1/dashboards", json={"name": "d1", "widgets": [widget]})
    assert created.status_code in (200, 201), created.text
    dashboard_id = created.json()["id"]
    assert client.get(f"/api/v1/dashboards/{dashboard_id}").json()["name"] == "d1"
    assert client.put(f"/api/v1/dashboards/{dashboard_id}", json={"name": "d1b", "widgets": [widget]}).json()["name"] == "d1b"
    assert client.post(f"/api/v1/dashboards/{dashboard_id}/clone").status_code in (200, 201)
    published = client.post(f"/api/v1/dashboards/{dashboard_id}/publish", params={"published": True})
    assert published.status_code == 200
    assert len(client.get("/api/v1/dashboards").json()) == 2
    assert client.get("/api/v1/dashboards/nope").status_code == 404


def test_pipeline_lifecycle_and_idempotent_run(client, dataset):
    payload = {"name": "rel", "dataset_id": dataset["id"], "pipeline_type": "relationships", "config": {"column": "revenue"}, "enabled": True}
    created = client.post("/api/v1/pipelines", json=payload)
    assert created.status_code in (200, 201), created.text
    pipeline_id = created.json()["id"]
    assert len(client.get("/api/v1/pipelines", params={"enabled": True}).json()) == 1
    first = client.post(f"/api/v1/pipelines/{pipeline_id}/run", json={"idempotency_key": "k1"})
    second = client.post(f"/api/v1/pipelines/{pipeline_id}/run", json={"idempotency_key": "k1"})
    assert first.status_code == 202 and first.json()["id"] == second.json()["id"]
    client.post(f"/api/v1/pipelines/{pipeline_id}/enabled", params={"enabled": False})
    assert client.post(f"/api/v1/pipelines/{pipeline_id}/run", json={"idempotency_key": "k2"}).status_code == 409


def test_lol_routes_reject_without_key(client, monkeypatch):
    monkeypatch.delenv("RIOT_API_KEY", raising=False)
    resolve = client.post("/api/v1/lol/accounts/resolve", json={"game_name": "a", "tag_line": "b"})
    assert resolve.status_code == 401
    collect = client.post("/api/v1/lol/matches/collect", json={"puuid": "p" * 30})
    assert collect.status_code == 401


def test_lol_process_unknown_match_is_client_error(client):
    response = client.post("/api/v1/lol/matches/process", json={"match_ids": ["KR_1"]})
    assert 400 <= response.status_code < 500


def test_match_ids_cannot_escape_the_data_root(client, data_root):
    """Regression: match_id was joined into a filesystem path without validation."""
    secret = data_root.parent / "secret" / "match.json"
    secret.parent.mkdir(exist_ok=True)
    secret.write_text('{"info": {"gameVersion": "1.1"}}', encoding="utf-8")
    for route in ("process", "process-grouped"):
        response = client.post(f"/api/v1/lol/matches/{route}", json={"match_ids": ["../../secret"]})
        assert response.status_code == 422, (route, response.text)
