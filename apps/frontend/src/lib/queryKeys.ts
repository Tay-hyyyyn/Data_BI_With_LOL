/** Centralized TanStack Query keys, so invalidation after a mutation can never typo a key. */
export const queryKeys = {
  datasets: ["datasets"] as const,
  profile: (id: string) => ["datasets", id, "profile"] as const,
  preview: (id: string, limit: number) => ["datasets", id, "preview", limit] as const,
  metrics: (datasetId?: string) => ["metrics", datasetId ?? "all"] as const,
  dashboards: ["dashboards"] as const,
  dashboard: (id: string) => ["dashboards", id] as const,
  jobs: ["jobs"] as const,
  pipelines: ["pipelines"] as const,
  datasetQuery: (id: string, payload: unknown) => ["datasets", id, "query", payload] as const,
  datasetChart: (id: string, payload: unknown) => ["datasets", id, "chart", payload] as const,
};
