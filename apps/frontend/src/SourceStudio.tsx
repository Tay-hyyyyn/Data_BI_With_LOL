import { useEffect, useState } from "react";
import { Database, Play, RefreshCw } from "lucide-react";
import { api } from "./api";
import type { DataSource, DataSourceStatus, Job } from "./types";

export function SourceStudio({ onSynced }: { onSynced: () => Promise<void> }) {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<DataSourceStatus | null>(null);
  const [acceptSchemaChange, setAcceptSchemaChange] = useState(false);
  const [sourceType, setSourceType] = useState<"sqlite_demo" | "postgresql">("sqlite_demo");
  const [name, setName] = useState("분석 DB 소스");
  const [tableName, setTableName] = useState("orders");
  const [primaryKey, setPrimaryKey] = useState("order_id");
  const [watermark, setWatermark] = useState("updated_at");
  const [urlEnv, setUrlEnv] = useState("REPORTING_DATABASE_URL");
  const load = async () => { const [nextSources, nextJobs] = await Promise.all([api.listSources(), api.listJobs()]); setSources(nextSources); setJobs(nextJobs.filter((job) => job.job_type === "source_sync")); };
  useEffect(() => { void load(); }, []);
  async function createDemo() {
    try {
      const existing = sources.find((source) => source.name === "내장 주문 분석 DB");
      if (!existing) await api.createSource({ name: "내장 주문 분석 DB", source_type: "sqlite_demo", table_name: "orders", primary_key: "order_id", watermark_column: "updated_at", enabled: true });
      await load(); setMessage("내장 SQLite 운영 DB를 등록했습니다. 이제 동기화하면 BI 데이터셋이 생성됩니다.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "데모 DB를 등록하지 못했습니다."); }
  }
  async function register() {
    try {
      await api.createSource({ name, source_type: sourceType, table_name: tableName, primary_key: primaryKey, watermark_column: watermark || null, connection_env_var: sourceType === "postgresql" ? urlEnv : null, enabled: true });
      await load(); setMessage("DB 소스를 등록했습니다. 등록 정보에는 연결 URL이나 비밀번호가 저장되지 않습니다.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "DB 소스를 등록하지 못했습니다."); }
  }
  async function sync(source: DataSource) {
    try {
      await api.syncSource(source.id, `manual-${Date.now()}`, source.dataset_id ? "incremental" : "full", acceptSchemaChange);
      await load(); await onSynced(); setMessage("읽기 전용 동기화 작업을 제출했습니다. 완료 후 데이터 허브에서 생성된 데이터셋을 확인하세요.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "동기화 작업을 시작하지 못했습니다."); }
  }
  async function toggle(source: DataSource) { await api.toggleSource(source.id, !source.enabled); await load(); }
  async function inspect(source: DataSource) { try { setStatus(await api.sourceStatus(source.id)); } catch (error) { setMessage(error instanceof Error ? error.message : "상태를 불러오지 못했습니다."); } }
  return <section className="studio">
    <div className="studio-toolbar"><div><p>DB → BI 데이터셋</p><h2>데이터 소스 동기화</h2></div><div className="widget-controls"><button className="primary" onClick={() => void createDemo()}><Database size={16}/> 내장 데모 DB 만들기</button><button onClick={() => void load()}><RefreshCw size={16}/> 새로고침</button></div></div>
    <div className="notice">현재는 실제 DB 없이도 검증 가능한 SQLite 주문 DB를 제공합니다. PostgreSQL은 연결 URL을 환경변수에만 보관하는 읽기 전용 소스로 등록할 수 있습니다.</div>
    {message && <div className="notice">{message}</div>}
    <div className="panel source-form"><h3>외부 DB 소스 등록</h3><div className="source-form-grid"><label>종류<select value={sourceType} onChange={(event) => setSourceType(event.target.value as "sqlite_demo" | "postgresql")}><option value="sqlite_demo">SQLite 데모</option><option value="postgresql">PostgreSQL</option></select></label><label>표시 이름<input value={name} onChange={(event) => setName(event.target.value)}/></label><label>테이블<input value={tableName} onChange={(event) => setTableName(event.target.value)}/></label><label>기본 키<input value={primaryKey} onChange={(event) => setPrimaryKey(event.target.value)}/></label><label>증분 기준 컬럼<input value={watermark} onChange={(event) => setWatermark(event.target.value)}/></label>{sourceType === "postgresql" && <label>URL 환경변수<input value={urlEnv} onChange={(event) => setUrlEnv(event.target.value)}/></label>}</div><button onClick={() => void register()}>DB 소스 등록</button></div>
    <label className="schema-accept"><input type="checkbox" checked={acceptSchemaChange} onChange={(event) => setAcceptSchemaChange(event.target.checked)}/> 원본 DB 컬럼 변경을 검토했으며 이번 동기화에서 수락합니다.</label>
    <div className="panel pipeline-list"><h3>등록된 DB 소스</h3>{sources.length === 0 ? <div className="recommend-placeholder">내장 데모 DB를 만들면 전체 동기화·증분 게시 흐름을 바로 시험할 수 있습니다.</div> : sources.map((source) => <div className="pipeline-row" key={source.id}><div><b>{source.name}</b><small>{source.source_type} · {source.table_name} · {source.dataset_id ? `${source.last_row_count}행 게시됨` : "아직 동기화하지 않음"}</small></div><button onClick={() => void inspect(source)}>상태</button><button onClick={() => void toggle(source)}>{source.enabled ? "활성" : "비활성"}</button><button disabled={!source.enabled} onClick={() => void sync(source)}><Play size={14}/> 동기화</button></div>)}</div>
    {status && <div className="panel source-status"><h3>{status.source.name} · 품질과 이력</h3>{status.quality ? <p>{status.quality.row_count.toLocaleString()}행 · {status.quality.column_count}열 · 평균 결측률 {(status.quality.null_ratio_mean * 100).toFixed(2)}%</p> : <p>아직 게시된 BI 버전이 없습니다.</p>}{status.quality_history.length > 0 && <div className="quality-history"><b>최근 품질 스냅샷</b>{status.quality_history.slice(0, 5).map((snapshot) => <small key={snapshot.created_at}>{new Date(snapshot.created_at).toLocaleString()} · {snapshot.row_count.toLocaleString()}행 · 결측 {(snapshot.null_ratio_mean * 100).toFixed(2)}%</small>)}</div>}<div className="source-events">{status.events.length === 0 ? <small>동기화 이력이 없습니다.</small> : status.events.map((event) => <div key={event.id}><b>{event.status}</b><span>{event.mode} · {event.synced_rows.toLocaleString()}행</span><small>{event.message ?? event.created_at}</small></div>)}</div></div>}
    <div className="panel job-list">{jobs.length === 0 ? <div className="recommend-placeholder">DB 동기화 실행 기록이 없습니다.</div> : jobs.map((job) => <div className="job-row" key={job.id}><span className={`job-status ${job.status}`}/><div><b>DB 동기화</b><small>{job.id.slice(0, 10)}</small></div><strong>{job.status}</strong><progress value={job.progress} max={100}/>{job.error && <em>{job.error}</em>}</div>)}</div>
  </section>;
}
