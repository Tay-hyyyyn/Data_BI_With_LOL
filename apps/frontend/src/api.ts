import type { Dashboard, Dataset, DatasetChartResult, DatasetQueryResult, Job, Pipeline, Preview, Profile, RelationshipResponse } from "./types";

async function decode<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "요청을 처리하지 못했습니다." }));
    throw new Error(payload.detail ?? "요청을 처리하지 못했습니다.");
  }
  return response.json() as Promise<T>;
}

export const api = {
  listDatasets: () => fetch("/api/v1/datasets").then(decode<Dataset[]>),
  profile: (id: string) => fetch(`/api/v1/datasets/${id}/profile`).then(decode<Profile>),
  preview: (id: string) => fetch(`/api/v1/datasets/${id}/preview?limit=100`).then(decode<Preview>),
  queryDataset: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/datasets/${id}/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<DatasetQueryResult>),
  chartDataset: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/datasets/${id}/chart`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<DatasetChartResult>),
  relationships: (id: string, column: string) =>
    fetch(`/api/v1/datasets/${id}/relationships`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ column }),
    }).then(decode<RelationshipResponse>),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch("/api/v1/datasets/upload", { method: "POST", body: form }).then(decode<Dataset>);
  },
  transform: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/datasets/${id}/transform`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Record<string, unknown>>),
  listDashboards: () => fetch("/api/v1/dashboards").then(decode<Dashboard[]>),
  getDashboard: (id: string) => fetch(`/api/v1/dashboards/${id}`).then(decode<Dashboard>),
  saveDashboard: (payload: Record<string, unknown>) =>
    fetch("/api/v1/dashboards", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Dashboard>),
  updateDashboard: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/dashboards/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Dashboard>),
  cloneDashboard: (id: string) => fetch(`/api/v1/dashboards/${id}/clone`, { method: "POST" }).then(decode<Dashboard>),
  publishDashboard: (id: string, published: boolean) => fetch(`/api/v1/dashboards/${id}/publish?published=${published}`, { method: "POST" }).then(decode<Dashboard>),
  listJobs: () => fetch("/api/v1/jobs").then(decode<Job[]>),
  queueRelationships: (id: string, column: string) =>
    fetch(`/api/v1/datasets/${id}/relationships/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ column }) }).then(decode<Job>),
  listPipelines: () => fetch("/api/v1/pipelines").then(decode<Pipeline[]>),
  createPipeline: (payload: Record<string, unknown>) => fetch("/api/v1/pipelines", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Pipeline>),
  togglePipeline: (id: string, enabled: boolean) => fetch(`/api/v1/pipelines/${id}/enabled?enabled=${enabled}`, { method: "POST" }).then(decode<Pipeline>),
  runPipeline: (id: string, idempotencyKey: string) => fetch(`/api/v1/pipelines/${id}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ idempotency_key: idempotencyKey }) }).then(decode<Job>),
};
