import { useEffect, useState } from "react";
import { Boxes, Play, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api } from "./api";
import type { AnalysisModel, AnalysisModelRun, Dataset, Job } from "./types";

type JoinDraft = { dataset_id: string; left_on: string; right_on: string; how: "left" | "inner"; cardinality: "" | "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many" };
const blankJoin = (): JoinDraft => ({ dataset_id: "", left_on: "id", right_on: "id", how: "left", cardinality: "" });

export function ModelStudio({ datasets, onBuilt }: { datasets: Dataset[]; onBuilt: () => Promise<void> }) {
  const [models, setModels] = useState<AnalysisModel[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<AnalysisModelRun[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [name, setName] = useState("새 분석 모델");
  const [base, setBase] = useState("");
  const [joins, setJoins] = useState<JoinDraft[]>([blankJoin()]);
  const [message, setMessage] = useState("");
  const load = async () => { const [nextModels, nextJobs] = await Promise.all([api.listModels(), api.listJobs()]); setModels(nextModels); setJobs(nextJobs.filter((job) => job.job_type === "analysis_model_build")); };
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (!base && datasets[0]) setBase(datasets[0].id); }, [datasets, base]);
  async function inspect(modelId: string) { setSelectedModel(modelId); try { setRuns(await api.listModelRuns(modelId)); } catch (error) { setMessage(error instanceof Error ? error.message : "모델 실행 이력을 불러오지 못했습니다."); } }
  function updateJoin(index: number, patch: Partial<JoinDraft>) { setJoins((items) => items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)); }
  async function create() {
    if (!name || !base) return;
    const activeJoins = joins.filter((join) => join.dataset_id && join.dataset_id !== base);
    try {
      await api.createModel({ name, base_dataset_id: base, joins: activeJoins.map((join) => ({ dataset_id: join.dataset_id, left_on: [join.left_on], right_on: [join.right_on], how: join.how, cardinality: join.cardinality || null })) });
      await load(); setJoins([blankJoin()]); setMessage("분석 모델을 등록했습니다. 빌드하면 독립적인 BI 데이터셋으로 게시됩니다.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "분석 모델을 등록하지 못했습니다."); }
  }
  async function build(model: AnalysisModel) { try { await api.buildModel(model.id); await load(); await onBuilt(); setMessage("모델 빌드 작업을 제출했습니다."); await inspect(model.id); } catch (error) { setMessage(error instanceof Error ? error.message : "모델을 빌드하지 못했습니다."); } }
  return <section className="studio"><div className="studio-toolbar"><div><p>재사용 가능한 분석 데이터셋</p><h2>데이터 모델</h2></div><button onClick={() => void load()}><RefreshCw size={16}/> 새로고침</button></div>{message && <div className="notice">{message}</div>}
    <div className="panel source-form"><h3>모델 등록</h3><div className="source-form-grid"><label>모델 이름<input value={name} onChange={(event) => setName(event.target.value)}/></label><label>기준 데이터셋<select value={base} onChange={(event) => setBase(event.target.value)}>{datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}</select></label></div><div className="model-joins"><b>조인 단계 · 최대 5개</b>{joins.map((join, index) => <div className="model-join" key={index}><span>{index + 1}</span><select value={join.dataset_id} onChange={(event) => updateJoin(index, { dataset_id: event.target.value })}><option value="">조인 없음</option>{datasets.filter((dataset) => dataset.id !== base).map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}</select><input aria-label={`조인 ${index + 1} 기준 키`} value={join.left_on} onChange={(event) => updateJoin(index, { left_on: event.target.value })} placeholder="기준 키"/><input aria-label={`조인 ${index + 1} 대상 키`} value={join.right_on} onChange={(event) => updateJoin(index, { right_on: event.target.value })} placeholder="대상 키"/><select value={join.how} onChange={(event) => updateJoin(index, { how: event.target.value as "left" | "inner" })}><option value="left">Left</option><option value="inner">Inner</option></select><select value={join.cardinality} onChange={(event) => updateJoin(index, { cardinality: event.target.value as JoinDraft["cardinality"] })}><option value="">카디널리티 미지정</option><option value="one_to_one">1:1</option><option value="one_to_many">1:N</option><option value="many_to_one">N:1</option><option value="many_to_many">N:N</option></select>{joins.length > 1 && <button aria-label={`조인 ${index + 1} 삭제`} onClick={() => setJoins((items) => items.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={15}/></button>}</div>)}</div><div className="widget-controls"><button onClick={() => joins.length < 5 && setJoins((items) => [...items, blankJoin()])} disabled={joins.length >= 5}><Plus size={16}/> 조인 추가</button><button className="primary" onClick={() => void create()}><Boxes size={16}/> 모델 등록</button></div></div>
    <div className="panel pipeline-list"><h3>등록된 분석 모델</h3>{models.length === 0 ? <div className="recommend-placeholder">기준 데이터셋과 조인 규칙을 저장하면, 원본 데이터를 바꾸지 않고 분석용 모델을 재빌드할 수 있습니다.</div> : models.map((model) => <div className="pipeline-row" key={model.id}><div><b>{model.name}</b><small>조인 {model.joins.length}개 · {model.output_dataset_id ? "게시 데이터셋 생성됨" : "아직 빌드하지 않음"}</small></div><button onClick={() => void inspect(model.id)}>이력</button><button onClick={() => void build(model)}><Play size={14}/> 빌드</button></div>)}</div>
    {selectedModel && <div className="panel model-runs"><h3>모델 실행 이력</h3>{runs.length === 0 ? <div className="recommend-placeholder">아직 실행 이력이 없습니다.</div> : runs.map((run) => <div key={run.id}><b>{run.status}</b><span>{run.row_count?.toLocaleString() ?? "—"}행 · {run.created_at}</span><small>입력 버전 {Object.values(run.input_versions).map((version) => version.slice(0, 8)).join(", ")}</small>{run.message && <em>{run.message}</em>}</div>)}</div>}
    <div className="panel job-list">{jobs.length === 0 ? <div className="recommend-placeholder">모델 빌드 실행 기록이 없습니다.</div> : jobs.map((job) => <div className="job-row" key={job.id}><span className={`job-status ${job.status}`}/><div><b>모델 빌드</b><small>{job.id.slice(0, 10)}</small></div><strong>{job.status}</strong><progress value={job.progress} max={100}/>{job.error && <em>{job.error}</em>}</div>)}</div>
  </section>;
}
