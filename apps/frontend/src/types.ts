export type Dataset = {
  id: string;
  name: string;
  source_type: string;
  created_at: string;
  current_version_id: string | null;
  row_count: number | null;
  column_count: number | null;
};

export type ColumnProfile = {
  name: string;
  dtype: string;
  semantic_type: "numeric" | "categorical" | "datetime" | "text" | "identifier";
  null_count: number;
  null_ratio: number;
  unique_count: number;
  sample_values: unknown[];
  minimum?: number | string | null;
  maximum?: number | string | null;
  mean?: number | null;
};

export type Profile = {
  dataset_id: string;
  version_id: string;
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
};

export type Preview = { columns: string[]; rows: Record<string, unknown>[] };

export type DatasetQueryResult = {
  dataset_id: string;
  version_id: string;
  dimension: string | null;
  measure: string | null;
  aggregation: string;
  rows: Array<{ category?: unknown; series?: unknown; value: number | null }>;
};

export type DatasetChartResult = {
  dataset_id: string;
  version_id: string;
  chart_type: string;
  sample_size: number;
  chart_spec: Record<string, unknown>;
};

export type Relationship = {
  column: string;
  relation_type: string;
  method: string;
  score: number;
  direction: "positive" | "negative" | "none";
  sample_size: number;
  null_ratio: number;
  reason: string;
  chart_spec: Record<string, unknown>;
};

export type RelationshipResponse = {
  selected_column: string;
  compared_candidates: number;
  sampled: boolean;
  items: Relationship[];
};

export type Dashboard = {
  id: string;
  name: string;
  widgets: Array<Record<string, unknown>>;
  filters: Array<Record<string, unknown>>;
  visibility: "private" | "published";
  created_at: string;
  updated_at: string;
};

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

export type Metric = {
  id: string;
  name: string;
  dataset_id: string;
  unit?: string | null;
  description?: string | null;
  value: number;
};

export type Job = {
  id: string;
  job_type: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type Pipeline = {
  id: string;
  name: string;
  dataset_id: string;
  pipeline_type: "relationships" | "transform";
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type DataSource = {
  id: string;
  name: string;
  source_type: "sqlite_demo" | "postgresql";
  table_name: string;
  primary_key: string;
  watermark_column: string | null;
  connection_env_var: string | null;
  enabled: boolean;
  dataset_id: string | null;
  last_watermark: string | null;
  last_synced_at: string | null;
  last_row_count: number;
  created_at: string;
  updated_at: string;
};

export type RiotAccount = { puuid: string; game_name: string; tag_line: string };
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
