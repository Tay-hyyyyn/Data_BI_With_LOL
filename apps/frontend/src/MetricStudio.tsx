import { useEffect, useState } from "react";
import { Plus, Sigma } from "lucide-react";
import { api } from "./api";
import type { Dataset, Metric, Profile } from "./types";

type Aggregation = "sum" | "mean" | "count" | "min" | "max" | "ratio";

export function MetricStudio({ dataset, profile }: { dataset: Dataset | null; profile: Profile | null }) {
  const [name, setName] = useState("");
  const [aggregation, setAggregation] = useState<Aggregation>("sum");
  const [column, setColumn] = useState("");
  const [numerator, setNumerator] = useState("");
  const [denominator, setDenominator] = useState("");
  const [unit, setUnit] = useState("");
  const [description, setDescription] = useState("");
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [message, setMessage] = useState("");
  const numeric = profile?.columns.filter((item) => item.semantic_type === "numeric") ?? [];

  async function load() { if (dataset) setMetrics(await api.listMetrics(dataset.id)); }
  useEffect(() => { setColumn(numeric[0]?.name ?? ""); setNumerator(numeric[0]?.name ?? ""); setDenominator(numeric[1]?.name ?? numeric[0]?.name ?? ""); void load().catch(() => setMetrics([])); }, [dataset?.id, profile?.version_id]);
  async function save() {
    if (!dataset || !name || (aggregation !== "count" && aggregation !== "ratio" && !column) || (aggregation === "ratio" && (!numerator || !denominator))) return;
    try { const metric = await api.saveMetric({ name, dataset_id: dataset.id, aggregation, column: aggregation === "count" || aggregation === "ratio" ? null : column, numerator: aggregation === "ratio" ? numerator : null, denominator: aggregation === "ratio" ? denominator : null, unit: unit || null, description: description || null }); setMessage(`${metric.name} 지표를 저장했습니다.`); setName(""); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "지표를 저장하지 못했습니다."); }
  }
  if (!dataset || !profile) return <section className="empty"><h2>먼저 데이터셋을 선택하세요</h2></section>;
  return <section className="studio"><div className="workspace-grid"><article className="panel"><div className="panel-head"><div><p>지표 정의</p><h2>재사용 가능한 KPI 만들기</h2></div><Sigma size={19}/></div><label>지표 이름<input value={name} onChange={(event) => setName(event.target.value)} placeholder="예: ROAS"/></label><label>집계<select value={aggregation} onChange={(event) => setAggregation(event.target.value as Aggregation)}><option value="sum">합계</option><option value="mean">평균</option><option value="count">행 수</option><option value="min">최솟값</option><option value="max">최댓값</option><option value="ratio">비율</option></select></label>{aggregation === "ratio" ? <div className="riot-id-row"><label>분자<select value={numerator} onChange={(event) => setNumerator(event.target.value)}>{numeric.map((item) => <option key={item.name}>{item.name}</option>)}</select></label><label>분모<select value={denominator} onChange={(event) => setDenominator(event.target.value)}>{numeric.map((item) => <option key={item.name}>{item.name}</option>)}</select></label></div> : aggregation !== "count" && <label>컬럼<select value={column} onChange={(event) => setColumn(event.target.value)}>{numeric.map((item) => <option key={item.name}>{item.name}</option>)}</select></label>}<div className="riot-id-row"><label>단위<input value={unit} onChange={(event) => setUnit(event.target.value)} placeholder="KRW, %, x"/></label><label>설명<input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="선택 사항"/></label></div><button className="primary" onClick={() => void save()}><Plus size={16}/> 지표 저장</button>{message && <div className="notice">{message}</div>}</article><article className="panel"><div className="panel-head"><div><p>현재 게시 버전</p><h2>저장된 지표</h2></div></div>{metrics.length === 0 ? <div className="recommend-placeholder">지표를 추가하면 현재 데이터 버전에서 다시 계산됩니다.</div> : <div className="kpis">{metrics.map((metric) => <article key={metric.id}><span>{metric.name}</span><strong>{new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(metric.value)}</strong><small>{metric.unit || "단위 없음"}{metric.description ? ` · ${metric.description}` : ""}</small></article>)}</div>}</article></div></section>;
}
