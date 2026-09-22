import { http, HttpResponse } from "msw";

/** Default mock responses for the backend. Tests override individual routes with `server.use(...)`. */
export const sampleDataset = {
  id: "ds-1",
  name: "마케팅 캠페인",
  source_type: "upload",
  created_at: "2026-01-01T00:00:00Z",
  current_version_id: "v-1",
  row_count: 2000,
  column_count: 9,
  version_number: 3,
};

export const sampleProfile = {
  dataset_id: "ds-1",
  version_id: "v-1",
  row_count: 2000,
  column_count: 9,
  columns: [
    {
      name: "channel",
      dtype: "object",
      semantic_type: "categorical",
      null_count: 0,
      null_ratio: 0,
      unique_count: 4,
      sample_values: ["search"],
    },
    {
      name: "revenue",
      dtype: "float64",
      semantic_type: "numeric",
      null_count: 0,
      null_ratio: 0,
      unique_count: 100,
      sample_values: [1],
    },
  ],
};

export const handlers = [
  http.get("/api/v1/datasets", () => HttpResponse.json([sampleDataset])),
  http.get("/api/v1/datasets/:id/profile", () => HttpResponse.json(sampleProfile)),
  http.get("/api/v1/datasets/:id/preview", () =>
    HttpResponse.json({
      columns: ["channel", "revenue"],
      rows: [{ channel: "search", revenue: 120 }],
    }),
  ),
  http.get("/api/v1/metrics", () => HttpResponse.json([])),
  http.get("/api/v1/dashboards", () => HttpResponse.json([])),
  http.get("/api/v1/jobs", () => HttpResponse.json([])),
  http.get("/api/v1/pipelines", () => HttpResponse.json([])),
];
