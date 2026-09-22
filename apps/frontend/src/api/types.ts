/**
 * Thin aliases over the generated OpenAPI schema. Never hand-edit field shapes here — regenerate
 * `generated.ts` with `pnpm gen:types` (after `python scripts/gen_openapi.py` from the repo root)
 * whenever the backend's Pydantic models change.
 */
import type { components } from "./generated";

export type Dataset = components["schemas"]["DatasetSummary"];
export type ColumnProfile = components["schemas"]["ColumnProfile"];
export type Profile = components["schemas"]["DatasetProfile"];
export type Preview = components["schemas"]["Preview"];
export type QueryResult = components["schemas"]["DatasetQueryResult"];
export type ChartResult = components["schemas"]["DatasetChartResult"];
export type Relationship = components["schemas"]["RelationshipItem"];
export type RelationshipResponse = components["schemas"]["RelationshipResponse"];
export type Dashboard = components["schemas"]["DashboardSummary"];
export type Metric = components["schemas"]["MetricSummary"];
export type Job = components["schemas"]["JobSummary"];
export type Pipeline = components["schemas"]["PipelineSummary"];
export type RiotAccount = components["schemas"]["RiotAccountSummary"];

export type QueryFilter = components["schemas"]["QueryFilter"];
export type DatasetQuery = components["schemas"]["DatasetQuery"];
export type DatasetChartRequest = components["schemas"]["DatasetChartRequest"];
export type MetricWrite = components["schemas"]["MetricWrite"];
export type PipelineWrite = components["schemas"]["PipelineWrite"];

/**
 * `DashboardSummary.widgets` is `list[dict[str, Any]]` on the backend (see
 * `apps/backend/app/schemas/dashboards.py`) — there is no server-side widget schema yet, so this
 * type cannot be generated. Keep it hand-written and validate defensively when reading a widget
 * back from a saved dashboard (see `features/dashboards/widgetOption.ts`).
 */
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

export function isDashboardWidget(value: unknown): value is DashboardWidget {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.id === "string" &&
    typeof record.type === "string" &&
    typeof record.column === "string"
  );
}

/** Raw shapes for LoL endpoints that return `-> dict` on the backend and so have no OpenAPI schema. */
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

export type LolMatchesProcessed = Record<string, Dataset>;
export type LolMatchesGrouped = {
  patches: Record<string, LolMatchesProcessed>;
  patch_stat_trend?: Dataset;
  sample_coverage?: Dataset;
};
