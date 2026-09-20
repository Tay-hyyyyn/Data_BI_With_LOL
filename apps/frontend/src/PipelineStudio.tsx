import { useEffect, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";
import { api } from "./api";
import type { Dataset, Job, Pipeline, Profile } from "./types";

export function PipelineStudio({ dataset, profile }: { dataset: Dataset | null; profile: Profile | null }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [column, setColumn] = useState("");
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [alerts, setAlerts] = useState<Array<{ kind: string; id: string; title: string; message: string | null; created_at: string }>>([]);
  const [message, setMessage] = useState("");
  const load = async () => { const [nextJobs, nextPipelines, nextAlerts] = await Promise.all([api.listJobs(), api.listPipelines(), api.listAlerts()]); setJobs(nextJobs); setPipelines(nextPipelines); setAlerts(nextAlerts); };
  useEffect(() => { void load(); }, []);
  useEffect(() => { setColumn(profile?.columns.find((item) => item.semantic_type === "numeric")?.name ?? ""); }, [profile?.version_id]);
  async function queue() { if (!dataset || !column) return; await api.queueRelationships(dataset.id, column); await load(); }
  async function register() { if (!dataset || !column) return; try { await api.createPipeline({ name: `${dataset.name} · ${column} 관계 갱신`, dataset_id: dataset.id, pipeline_type: "relationships", config: { column }, enabled: true }); await load(); setMessage("Airflow가 조회할 활성 파이프라인을 등록했습니다."); } catch (error) { setMessage(error instanceof Error ? error.message : "등록하지 못했습니다."); } }
  async function toggle(pipeline: Pipeline) { await api.togglePipeline(pipeline.id, !pipeline.enabled); await load(); }
  async function run(pipeline: Pipeline) { try { await api.runPipeline(pipeline.id, `manual-${Date.now()}`); await load(); setMessage("파이프라인 작업을 제출했습니다."); } catch (error) { setMessage(error instanceof Error ? error.message : "실행하지 못했습니다."); } }
  return <section className="studio"><div className="studio-toolbar"><div><p>로컬 작업 실행기</p><h2>비동기 분석 작업</h2></div><div className="widget-controls"><select value={column} onChange={(event) => setColumn(event.target.value)}>{profile?.columns.filter((item) => !["identifier", "text"].includes(item.semantic_type)).map((item) => <option key={item.name}>{item.name}</option>)}</select><button className="primary" onClick={() => void queue()}><Activity size={16}/> 한 번 실행</button><button onClick={() => void register()}>파이프라인 등록</button><button onClick={() => void load()}><RefreshCw size={16}/> 새로고침</button></div></div>{message && <div className="notice">{message}</div>}<div className="panel operation-alerts"><h3>운영 알림</h3>{alerts.length === 0 ? <div className="recommend-placeholder">실패한 작업이나 검토할 스키마 변경이 없습니다.</div> : alerts.map((alert) => <div key={`${alert.kind}-${alert.id}`}><b>{alert.kind}</b><span>{alert.title}</span><small>{alert.message || alert.created_at}</small></div>)}</div><div className="panel pipeline-list"><h3>등록 파이프라인</h3>{pipelines.length === 0 ? <div className="recommend-placeholder">등록된 파이프라인이 없습니다.</div> : pipelines.map((pipeline) => <div className="pipeline-row" key={pipeline.id}><div><b>{pipeline.name}</b><small>{pipeline.pipeline_type} · {pipeline.id.slice(0, 10)}</small></div><button onClick={() => void toggle(pipeline)}>{pipeline.enabled ? "활성" : "비활성"}</button><button disabled={!pipeline.enabled} onClick={() => void run(pipeline)}>실행</button></div>)}</div><div className="panel job-list">{jobs.length === 0 ? <div className="recommend-placeholder">실행 기록이 없습니다.</div> : jobs.map((job) => <div className="job-row" key={job.id}><span className={`job-status ${job.status}`}/><div><b>{job.job_type}</b><small>{job.id.slice(0, 10)}</small></div><strong>{job.status}</strong><progress value={job.progress} max={100}/>{job.error && <em>{job.error}</em>}</div>)}</div></section>;
}
