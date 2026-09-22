/** Typed wrappers around every backend route. Feature code calls these (directly or via `lib/queries`), never `fetch`. */
import { apiGet, apiPost, apiPut, apiUpload } from "../lib/apiClient";
import type {
  ChartResult,
  Dashboard,
  Dataset,
  DatasetChartRequest,
  DatasetQuery,
  Job,
  LolMatchesGrouped,
  LolMatchesProcessed,
  LolStaticSync,
  Metric,
  MetricWrite,
  Pipeline,
  PipelineWrite,
  Preview,
  Profile,
  QueryResult,
  RelationshipResponse,
  RiotAccount,
  RiotMatchCollection,
} from "./types";

export const datasetsApi = {
  list: () => apiGet<Dataset[]>("/api/v1/datasets"),
  profile: (id: string) => apiGet<Profile>(`/api/v1/datasets/${id}/profile`),
  preview: (id: string, limit = 100) =>
    apiGet<Preview>(`/api/v1/datasets/${id}/preview?limit=${limit}`),
  upload: (file: File, name?: string) =>
    apiUpload<Dataset>("/api/v1/datasets/upload", file, name ? { name } : {}),
  query: (id: string, payload: DatasetQuery) =>
    apiPost<QueryResult>(`/api/v1/datasets/${id}/query`, payload),
  chart: (id: string, payload: DatasetChartRequest) =>
    apiPost<ChartResult>(`/api/v1/datasets/${id}/chart`, payload),
  relationships: (id: string, payload: Record<string, unknown>) =>
    apiPost<RelationshipResponse>(`/api/v1/datasets/${id}/relationships`, payload),
  queueRelationships: (id: string, column: string) =>
    apiPost<Job>(`/api/v1/datasets/${id}/relationships/jobs`, { column }),
  transform: (id: string, payload: Record<string, unknown>) =>
    apiPost<{ version_number: number }>(`/api/v1/datasets/${id}/transform`, payload),
};

export const metricsApi = {
  list: (datasetId?: string) =>
    apiGet<Metric[]>(
      `/api/v1/metrics${datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ""}`,
    ),
  save: (payload: MetricWrite) => apiPost<Metric>("/api/v1/metrics", payload),
};

export const dashboardsApi = {
  list: () => apiGet<Dashboard[]>("/api/v1/dashboards"),
  get: (id: string) => apiGet<Dashboard>(`/api/v1/dashboards/${id}`),
  save: (payload: Record<string, unknown>) => apiPost<Dashboard>("/api/v1/dashboards", payload),
  update: (id: string, payload: Record<string, unknown>) =>
    apiPut<Dashboard>(`/api/v1/dashboards/${id}`, payload),
  clone: (id: string) => apiPost<Dashboard>(`/api/v1/dashboards/${id}/clone`),
  publish: (id: string, published: boolean) =>
    apiPost<Dashboard>(`/api/v1/dashboards/${id}/publish?published=${published}`),
};

export const jobsApi = {
  list: () => apiGet<Job[]>("/api/v1/jobs"),
};

export const pipelinesApi = {
  list: () => apiGet<Pipeline[]>("/api/v1/pipelines"),
  create: (payload: PipelineWrite) => apiPost<Pipeline>("/api/v1/pipelines", payload),
  setEnabled: (id: string, enabled: boolean) =>
    apiPost<Pipeline>(`/api/v1/pipelines/${id}/enabled?enabled=${enabled}`),
  run: (id: string, idempotencyKey: string) =>
    apiPost<Job>(`/api/v1/pipelines/${id}/run`, { idempotency_key: idempotencyKey }),
};

export const lolApi = {
  syncStatic: (version?: string) =>
    apiPost<LolStaticSync>("/api/v1/lol/static/sync", {
      version: version || null,
      bootstrap_samples: 200,
    }),
  createStarterDashboard: (patch: string) =>
    apiPost<Dashboard>("/api/v1/lol/dashboards/starter", { patch }),
  createPatchTrendDashboard: () => apiPost<Dashboard>("/api/v1/lol/dashboards/patch-trend"),
  uploadBenchmark: (file: File) => apiUpload<Dataset>("/api/v1/lol/benchmarks/upload", file),
  resolveAccount: (gameName: string, tagLine: string) =>
    apiPost<RiotAccount>("/api/v1/lol/accounts/resolve", {
      game_name: gameName,
      tag_line: tagLine,
    }),
  collectMatches: (puuid: string, count: number) =>
    apiPost<RiotMatchCollection>("/api/v1/lol/matches/collect", { puuid, count }),
  processMatches: (matchIds: string[], itemDatasetId?: string) =>
    apiPost<LolMatchesProcessed>("/api/v1/lol/matches/process", {
      match_ids: matchIds,
      snapshot_minutes: [10, 15, 20],
      item_dataset_id: itemDatasetId || null,
    }),
  processMatchesGrouped: (matchIds: string[]) =>
    apiPost<LolMatchesGrouped>("/api/v1/lol/matches/process-grouped", {
      match_ids: matchIds,
      snapshot_minutes: [10, 15, 20],
    }),
};
