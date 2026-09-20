import type { AnalysisModel, AnalysisModelRun, AuthStatus, Dashboard, DashboardShare, DataSource, DataSourceStatus, Dataset, DatasetChartResult, DatasetQueryResult, Job, LolStaticSync, Metric, Pipeline, Preview, Profile, RelationshipResponse, RiotAccount, RiotMatchCollection } from "./types";

async function decode<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "요청을 처리하지 못했습니다." }));
    throw new Error(payload.detail ?? "요청을 처리하지 못했습니다.");
  }
  return response.json() as Promise<T>;
}

export const api = {
  authStatus: () => fetch("/api/v1/auth/me").then(decode<AuthStatus>),
  login: (email: string, password: string) => fetch("/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) }).then(decode<AuthStatus>),
  logout: () => fetch("/api/v1/auth/logout", { method: "POST" }),
  listDatasets: () => fetch("/api/v1/datasets").then(decode<Dataset[]>),
  profile: (id: string) => fetch(`/api/v1/datasets/${id}/profile`).then(decode<Profile>),
  preview: (id: string) => fetch(`/api/v1/datasets/${id}/preview?limit=100`).then(decode<Preview>),
  queryDataset: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/datasets/${id}/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<DatasetQueryResult>),
  chartDataset: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/datasets/${id}/chart`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<DatasetChartResult>),
  relationships: (id: string, column: string, options: Record<string, unknown> = {}) =>
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
  transform: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/datasets/${id}/transform`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Record<string, unknown>>),
  listMetrics: (datasetId?: string) => fetch(`/api/v1/metrics${datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ""}`).then(decode<Metric[]>),
  saveMetric: (payload: Record<string, unknown>) => fetch("/api/v1/metrics", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Metric>),
  listDashboards: () => fetch("/api/v1/dashboards").then(decode<Dashboard[]>),
  getDashboard: (id: string) => fetch(`/api/v1/dashboards/${id}`).then(decode<Dashboard>),
  saveDashboard: (payload: Record<string, unknown>) =>
    fetch("/api/v1/dashboards", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Dashboard>),
  createMarketingStarterDashboard: (datasetId: string) =>
    fetch(`/api/v1/dashboards/starters/marketing?dataset_id=${encodeURIComponent(datasetId)}`, { method: "POST" }).then(decode<Dashboard>),
  updateDashboard: (id: string, payload: Record<string, unknown>) =>
    fetch(`/api/v1/dashboards/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Dashboard>),
  cloneDashboard: (id: string) => fetch(`/api/v1/dashboards/${id}/clone`, { method: "POST" }).then(decode<Dashboard>),
  publishDashboard: (id: string, published: boolean) => fetch(`/api/v1/dashboards/${id}/publish?published=${published}`, { method: "POST" }).then(decode<Dashboard>),
  createDashboardShare: (id: string) => fetch(`/api/v1/dashboards/${id}/shares`, { method: "POST" }).then(decode<DashboardShare>),
  getSharedDashboard: (token: string) => fetch(`/api/v1/dashboard-shares/${encodeURIComponent(token)}`).then(decode<Dashboard>),
  revokeDashboardShare: (token: string) => fetch(`/api/v1/dashboard-shares/${encodeURIComponent(token)}`, { method: "DELETE" }),
  listJobs: () => fetch("/api/v1/jobs").then(decode<Job[]>),
  listAlerts: () => fetch("/api/v1/operations/alerts").then(decode<Array<{ kind: string; id: string; title: string; message: string | null; created_at: string }>>),
  queueRelationships: (id: string, column: string) =>
    fetch(`/api/v1/datasets/${id}/relationships/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ column }) }).then(decode<Job>),
  listPipelines: () => fetch("/api/v1/pipelines").then(decode<Pipeline[]>),
  createPipeline: (payload: Record<string, unknown>) => fetch("/api/v1/pipelines", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<Pipeline>),
  togglePipeline: (id: string, enabled: boolean) => fetch(`/api/v1/pipelines/${id}/enabled?enabled=${enabled}`, { method: "POST" }).then(decode<Pipeline>),
  runPipeline: (id: string, idempotencyKey: string) => fetch(`/api/v1/pipelines/${id}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ idempotency_key: idempotencyKey }) }).then(decode<Job>),
  listSources: () => fetch("/api/v1/sources").then(decode<DataSource[]>),
  createSource: (payload: Record<string, unknown>) => fetch("/api/v1/sources", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<DataSource>),
  toggleSource: (id: string, enabled: boolean) => fetch(`/api/v1/sources/${id}/enabled?enabled=${enabled}`, { method: "POST" }).then(decode<DataSource>),
  sourceStatus: (id: string) => fetch(`/api/v1/sources/${id}/status`).then(decode<DataSourceStatus>),
  syncSource: (id: string, idempotencyKey: string, mode: "full" | "incremental", acceptSchemaChange = false) => fetch(`/api/v1/sources/${id}/sync`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ idempotency_key: idempotencyKey, mode, accept_schema_change: acceptSchemaChange }) }).then(decode<Job>),
  listModels: () => fetch("/api/v1/models").then(decode<AnalysisModel[]>),
  createModel: (payload: Record<string, unknown>) => fetch("/api/v1/models", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(decode<AnalysisModel>),
  buildModel: (id: string) => fetch(`/api/v1/models/${id}/build`, { method: "POST" }).then(decode<Job>),
  listModelRuns: (id: string) => fetch(`/api/v1/models/${id}/runs`).then(decode<AnalysisModelRun[]>),
  syncLolStatic: (version?: string) => fetch("/api/v1/lol/static/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version: version || null, bootstrap_samples: 200 }) }).then(decode<LolStaticSync>),
  createLolStarterDashboard: (patch: string) => fetch("/api/v1/lol/dashboards/starter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ patch }) }).then(decode<Dashboard>),
  createLolPatchTrendDashboard: () => fetch("/api/v1/lol/dashboards/patch-trend", { method: "POST" }).then(decode<Dashboard>),
  createLolCaseStudyDashboard: () => fetch("/api/v1/lol/dashboards/case-study", { method: "POST" }).then(decode<Dashboard>),
  uploadLolpsBenchmark: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch("/api/v1/lol/benchmarks/upload", { method: "POST", body: form }).then(decode<Dataset>);
  },
  resolveRiotAccount: (gameName: string, tagLine: string) => fetch("/api/v1/lol/accounts/resolve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ game_name: gameName, tag_line: tagLine }) }).then(decode<RiotAccount>),
  collectLolMatches: (puuid: string, count: number) => fetch("/api/v1/lol/matches/collect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ puuid, count }) }).then(decode<RiotMatchCollection>),
  processLolMatches: (matchIds: string[], itemDatasetId?: string) => fetch("/api/v1/lol/matches/process", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ match_ids: matchIds, snapshot_minutes: [10, 15, 20], item_dataset_id: itemDatasetId || null }) }).then(decode<Record<string, Dataset>>),
  processLolMatchesGrouped: (matchIds: string[]) => fetch("/api/v1/lol/matches/process-grouped", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ match_ids: matchIds, snapshot_minutes: [10, 15, 20] }) }).then(decode<{ patches: Record<string, Record<string, Dataset>>; patch_stat_trend?: Dataset; sample_coverage?: Dataset }>),
};
