/**
 * TanStack Query hooks. Replaces the manual `useEffect` fetch/cancel dances and the ad-hoc
 * `onPublished` cache-invalidation callback that used to live in `App.tsx`.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { dashboardsApi, datasetsApi, jobsApi, metricsApi, pipelinesApi } from "../api/endpoints";
import type {
  ChartResult,
  Dashboard,
  Dataset,
  DatasetChartRequest,
  DatasetQuery,
  Job,
  Metric,
  MetricWrite,
  Pipeline,
  PipelineWrite,
  Preview,
  Profile,
  QueryResult,
} from "../api/types";
import { queryKeys } from "./queryKeys";

export function useDatasets(): UseQueryResult<Dataset[]> {
  return useQuery({ queryKey: queryKeys.datasets, queryFn: datasetsApi.list });
}

export function useProfile(datasetId: string | undefined): UseQueryResult<Profile> {
  return useQuery({
    queryKey: queryKeys.profile(datasetId ?? ""),
    queryFn: () => datasetsApi.profile(datasetId as string),
    enabled: Boolean(datasetId),
  });
}

export function usePreview(datasetId: string | undefined, limit = 100): UseQueryResult<Preview> {
  return useQuery({
    queryKey: queryKeys.preview(datasetId ?? "", limit),
    queryFn: () => datasetsApi.preview(datasetId as string, limit),
    enabled: Boolean(datasetId),
  });
}

export function useDatasetQuery(
  datasetId: string | undefined,
  payload: DatasetQuery | null,
): UseQueryResult<QueryResult> {
  return useQuery({
    queryKey: queryKeys.datasetQuery(datasetId ?? "", payload),
    queryFn: () => datasetsApi.query(datasetId as string, payload as DatasetQuery),
    enabled: Boolean(datasetId && payload),
  });
}

export function useDatasetChart(
  datasetId: string | undefined,
  payload: DatasetChartRequest | null,
): UseQueryResult<ChartResult> {
  return useQuery({
    queryKey: queryKeys.datasetChart(datasetId ?? "", payload),
    queryFn: () => datasetsApi.chart(datasetId as string, payload as DatasetChartRequest),
    enabled: Boolean(datasetId && payload),
  });
}

export function useUploadDataset() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name }: { file: File; name?: string }) => datasetsApi.upload(file, name),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.datasets }),
  });
}

/** Invalidates profile/preview/dataset-list for `datasetId` — the replacement for the old `onPublished` callback. */
export function useInvalidateDataset() {
  const client = useQueryClient();
  return (datasetId: string) => {
    client.invalidateQueries({ queryKey: queryKeys.datasets });
    client.invalidateQueries({ queryKey: ["datasets", datasetId] });
  };
}

export function useMetrics(datasetId: string | undefined): UseQueryResult<Metric[]> {
  return useQuery({
    queryKey: queryKeys.metrics(datasetId),
    queryFn: () => metricsApi.list(datasetId),
  });
}

export function useSaveMetric() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: MetricWrite) => metricsApi.save(payload),
    onSuccess: (_, payload) =>
      client.invalidateQueries({ queryKey: queryKeys.metrics(payload.dataset_id) }),
  });
}

export function useDashboards(): UseQueryResult<Dashboard[]> {
  return useQuery({ queryKey: queryKeys.dashboards, queryFn: dashboardsApi.list });
}

export function useDashboard(id: string | undefined): UseQueryResult<Dashboard> {
  return useQuery({
    queryKey: queryKeys.dashboard(id ?? ""),
    queryFn: () => dashboardsApi.get(id as string),
    enabled: Boolean(id),
  });
}

export function useSaveDashboard() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => dashboardsApi.save(payload),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.dashboards }),
  });
}

export function useUpdateDashboard() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      dashboardsApi.update(id, payload),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.dashboards }),
  });
}

export function useCloneDashboard() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => dashboardsApi.clone(id),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.dashboards }),
  });
}

export function usePublishDashboard() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, published }: { id: string; published: boolean }) =>
      dashboardsApi.publish(id, published),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.dashboards }),
  });
}

export function useJobs(): UseQueryResult<Job[]> {
  return useQuery({ queryKey: queryKeys.jobs, queryFn: jobsApi.list, refetchInterval: 4_000 });
}

export function usePipelines(): UseQueryResult<Pipeline[]> {
  return useQuery({ queryKey: queryKeys.pipelines, queryFn: pipelinesApi.list });
}

export function useCreatePipeline() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: PipelineWrite) => pipelinesApi.create(payload),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.pipelines }),
  });
}

export function useSetPipelineEnabled() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      pipelinesApi.setEnabled(id, enabled),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.pipelines }),
  });
}

export function useRunPipeline() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, idempotencyKey }: { id: string; idempotencyKey: string }) =>
      pipelinesApi.run(id, idempotencyKey),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.jobs }),
  });
}
