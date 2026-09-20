import type { components } from "./api.generated";

type ApiSchema = components["schemas"];

// These aliases are generated from FastAPI's OpenAPI contract. UI-only models stay below.
export type Dataset = ApiSchema["DatasetSummary"];
export type ColumnProfile = ApiSchema["ColumnProfile"];
export type Profile = ApiSchema["DatasetProfile"];

export type Preview = { columns: string[]; rows: Record<string, unknown>[] };

export type DatasetQueryResult = ApiSchema["DatasetQueryResult"];
export type DatasetChartResult = ApiSchema["DatasetChartResult"];
export type Relationship = ApiSchema["RelationshipItem"];
export type RelationshipResponse = ApiSchema["RelationshipResponse"];

export type Dashboard = ApiSchema["DashboardSummary"];

export type DashboardWidget = {
  id: string;
  title: string;
  type: "kpi" | "bar" | "line" | "histogram" | "scatter" | "boxplot" | "heatmap";
  column: string;
  dimension?: string;
  series?: string;
  secondary?: string;
  aggregation?: "sum" | "mean" | "count" | "min" | "max";
  dataset_id?: string;
};

export type Metric = ApiSchema["MetricSummary"];
export type Job = ApiSchema["JobSummary"];
export type Pipeline = ApiSchema["PipelineSummary"];
export type RiotAccount = ApiSchema["RiotAccountSummary"];

export type DatasetQueryRequest = Partial<ApiSchema["DatasetQuery"]>;
export type DatasetChartRequest = Partial<ApiSchema["DatasetChartRequest"]>;
export type RelationshipRequest = Partial<Omit<ApiSchema["RelationshipRequest"], "column">>;
export type TransformRequest = ApiSchema["TransformRequest"];
export type MetricWrite = ApiSchema["MetricWrite"];
export type DashboardWrite = ApiSchema["DashboardWrite"];
export type PipelineWrite = ApiSchema["PipelineWrite"];
export type LolStaticSyncRequest = Partial<ApiSchema["LolStaticSyncRequest"]>;
export type RiotAccountResolveRequest = ApiSchema["RiotAccountResolveRequest"];
export type RiotMatchCollectRequest = ApiSchema["RiotMatchCollectRequest"];
export type RiotMatchProcessRequest = ApiSchema["RiotMatchProcessRequest"];
export type LolStaticSync = {
  patch: string;
  items: Dataset;
  champions: Dataset;
  runes: Dataset;
  stat_values: Dataset;
};
export type RiotMatchCollection = {
  visibility: "private";
  fetched: number;
  cached: number;
  matches: Array<{ match_id: string; cached: boolean; files: string[] }>;
};
