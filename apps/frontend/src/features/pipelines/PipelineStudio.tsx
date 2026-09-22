import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useActiveDataset } from "../../app/DatasetContext";
import { datasetsApi } from "../../api/endpoints";
import type { Pipeline } from "../../api/types";
import { useToast } from "../../components/Toast";
import { errorMessage } from "../../lib/apiClient";
import { queryKeys } from "../../lib/queryKeys";
import {
  useCreatePipeline,
  useJobs,
  usePipelines,
  useProfile,
  useRunPipeline,
  useSetPipelineEnabled,
} from "../../lib/queries";

export function PipelineStudio() {
  const { active } = useActiveDataset();
  const { data: profile } = useProfile(active?.id);
  const { data: jobs = [] } = useJobs();
  const { data: pipelines = [], refetch: refetchPipelines } = usePipelines();
  const { notify } = useToast();
  const client = useQueryClient();

  const [column, setColumn] = useState("");
  useEffect(() => {
    setColumn(profile?.columns.find((item) => item.semantic_type === "numeric")?.name ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset the column pick only when the dataset version changes
  }, [profile?.version_id]);

  const queueOnce = useMutation({
    mutationFn: () => datasetsApi.queueRelationships(active!.id, column),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.jobs }),
    onError: (error) => notify(errorMessage(error, "실행하지 못했습니다."), "error"),
  });
  const register = useCreatePipeline();
  const toggle = useSetPipelineEnabled();
  const run = useRunPipeline();

  async function handleRegister() {
    if (!active || !column) return;
    try {
      await register.mutateAsync({
        name: `${active.name} · ${column} 관계 갱신`,
        dataset_id: active.id,
        pipeline_type: "relationships",
        config: { column },
        enabled: true,
      });
      notify("Airflow가 조회할 활성 파이프라인을 등록했습니다.");
    } catch (error) {
      notify(errorMessage(error, "등록하지 못했습니다."), "error");
    }
  }

  async function handleRun(pipeline: Pipeline) {
    try {
      await run.mutateAsync({ id: pipeline.id, idempotencyKey: `manual-${Date.now()}` });
      notify("파이프라인 작업을 제출했습니다.");
    } catch (error) {
      notify(errorMessage(error, "실행하지 못했습니다."), "error");
    }
  }

  return (
    <section className="studio">
      <div className="studio-toolbar">
        <div>
          <p>로컬 작업 실행기</p>
          <h2>비동기 분석 작업</h2>
        </div>
        <div className="widget-controls">
          <select value={column} onChange={(event) => setColumn(event.target.value)}>
            {profile?.columns
              .filter((item) => !["identifier", "text"].includes(item.semantic_type))
              .map((item) => (
                <option key={item.name}>{item.name}</option>
              ))}
          </select>
          <button
            className="primary"
            disabled={!active || !column}
            onClick={() => queueOnce.mutate()}
          >
            <Activity size={16} /> 한 번 실행
          </button>
          <button disabled={!active || !column} onClick={() => void handleRegister()}>
            파이프라인 등록
          </button>
          <button onClick={() => void refetchPipelines()}>
            <RefreshCw size={16} /> 새로고침
          </button>
        </div>
      </div>
      <div className="panel pipeline-list">
        <h3>등록 파이프라인</h3>
        {pipelines.length === 0 ? (
          <div className="recommend-placeholder">등록된 파이프라인이 없습니다.</div>
        ) : (
          pipelines.map((pipeline) => (
            <div className="pipeline-row" key={pipeline.id}>
              <div>
                <b>{pipeline.name}</b>
                <small>
                  {pipeline.pipeline_type} · {pipeline.id.slice(0, 10)}
                </small>
              </div>
              <button
                onClick={() => toggle.mutate({ id: pipeline.id, enabled: !pipeline.enabled })}
              >
                {pipeline.enabled ? "활성" : "비활성"}
              </button>
              <button disabled={!pipeline.enabled} onClick={() => void handleRun(pipeline)}>
                실행
              </button>
            </div>
          ))
        )}
      </div>
      <div className="panel job-list">
        {jobs.length === 0 ? (
          <div className="recommend-placeholder">실행 기록이 없습니다.</div>
        ) : (
          jobs.map((job) => (
            <div className="job-row" key={job.id}>
              <span className={`job-status ${job.status}`} />
              <div>
                <b>{job.job_type}</b>
                <small>{job.id.slice(0, 10)}</small>
              </div>
              <strong>{job.status}</strong>
              <progress value={job.progress} max={100} />
              {job.error && <em>{job.error}</em>}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
