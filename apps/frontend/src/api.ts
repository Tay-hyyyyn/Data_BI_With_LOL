import type { Dashboard, DashboardWrite, Dataset, DatasetChartRequest, DatasetChartResult, DatasetQueryRequest, DatasetQueryResult, Job, LolStaticSync, LolStaticSyncRequest, Metric, MetricWrite, Pipeline, PipelineWrite, Preview, Profile, RelationshipRequest, RelationshipResponse, RiotAccount, RiotAccountResolveRequest, RiotMatchCollection, RiotMatchCollectRequest, RiotMatchProcessRequest, TransformRequest } from "./types";

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
  queryDataset: (id: string, payload: DatasetQueryRequest) =>
    fetch(`/api/v1/datasets/${id}/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<DatasetQueryResult>),
  chartDataset: (id: string, payload: DatasetChartRequest) =>
    fetch(`/api/v1/datasets/${id}/chart`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<DatasetChartResult>),
  relationships: (id: string, column: string, options: RelationshipRequest = {}) =>
    fetch(`/api/v1/datasets/${id}/relationships`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ column, ...options }),
    }).then(decode<RelationshipResponse>),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch("/api/v1/datasets/upload", { method: "POST", body: form }).then(decode<Dataset>);
  },
  transform: (id: string, payload: TransformRequest) =>
    fetch(`/api/v1/datasets/${id}/transform`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Record<string, unknown>>),
  listMetrics: (datasetId?: string) => fetch(`/api/v1/metrics${datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ""}`).then(decode<Metric[]>),
  saveMetric: (payload: MetricWrite) => fetch("/api/v1/metrics", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Metric>),
  listDashboards: () => fetch("/api/v1/dashboards").then(decode<Dashboard[]>),
  getDashboard: (id: string) => fetch(`/api/v1/dashboards/${id}`).then(decode<Dashboard>),
  saveDashboard: (payload: DashboardWrite) =>
    fetch("/api/v1/dashboards", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Dashboard>),
  updateDashboard: (id: string, payload: DashboardWrite) =>
    fetch(`/api/v1/dashboards/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Dashboard>),
  cloneDashboard: (id: string) => fetch(`/api/v1/dashboards/${id}/clone`, { method: "POST" }).then(decode<Dashboard>),
  publishDashboard: (id: string, published: boolean) => fetch(`/api/v1/dashboards/${id}/publish?published=${published}`, { method: "POST" }).then(decode<Dashboard>),
  listJobs: () => fetch("/api/v1/jobs").then(decode<Job[]>),
  queueRelationships: (id: string, column: string) =>
    fetch(`/api/v1/datasets/${id}/relationships/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ column }) }).then(decode<Job>),
  listPipelines: () => fetch("/api/v1/pipelines").then(decode<Pipeline[]>),
  createPipeline: (payload: PipelineWrite) => fetch("/api/v1/pipelines", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Pipeline>),
  togglePipeline: (id: string, enabled: boolean) => fetch(`/api/v1/pipelines/${id}/enabled?enabled=${enabled}`, { method: "POST" }).then(decode<Pipeline>),
  runPipeline: (id: string, idempotencyKey: string) => fetch(`/api/v1/pipelines/${id}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ idempotency_key: idempotencyKey }) }).then(decode<Job>),
  syncLolStatic: (version?: string) => {
    const payload: LolStaticSyncRequest = { version: version || null, bootstrap_samples: 200 };
    return fetch("/api/v1/lol/static/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<LolStaticSync>);
  },
  createLolStarterDashboard: (patch: string) => fetch("/api/v1/lol/dashboards/starter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ patch }) }).then(decode<Dashboard>),
  createLolPatchTrendDashboard: () => fetch("/api/v1/lol/dashboards/patch-trend", { method: "POST" }).then(decode<Dashboard>),
  uploadLolpsBenchmark: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch("/api/v1/lol/benchmarks/upload", { method: "POST", body: form }).then(decode<Dataset>);
  },
  resolveRiotAccount: (gameName: string, tagLine: string) => {
    const payload: RiotAccountResolveRequest = { game_name: gameName, tag_line: tagLine };
    return fetch("/api/v1/lol/accounts/resolve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<RiotAccount>);
  },
  collectLolMatches: (puuid: string, count: number) => {
    const payload: RiotMatchCollectRequest = { puuid, count };
    return fetch("/api/v1/lol/matches/collect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<RiotMatchCollection>);
  },
  processLolMatches: (matchIds: string[], itemDatasetId?: string) => {
    const payload: RiotMatchProcessRequest = { match_ids: matchIds, snapshot_minutes: [10, 15, 20], item_dataset_id: itemDatasetId || null };
    return fetch("/api/v1/lol/matches/process", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Record<string, Dataset>>);
  },
  processLolMatchesGrouped: (matchIds: string[]) => {
    const payload: RiotMatchProcessRequest = { match_ids: matchIds, snapshot_minutes: [10, 15, 20] };
    return fetch("/api/v1/lol/matches/process-grouped", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<{ patches: Record<string, Record<string, Dataset>>; patch_stat_trend?: Dataset; sample_coverage?: Dataset }>);
  },
};
