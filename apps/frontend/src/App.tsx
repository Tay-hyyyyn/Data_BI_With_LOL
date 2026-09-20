import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowUpRight, BarChart3, Boxes, Database, FileUp, Gamepad2, Link2, LoaderCircle, LogOut, Search, Sigma, Sparkles, Table2 } from "lucide-react";
import { api } from "./api";
import type { EChartsCoreOption } from "echarts/core";
import type { AuthStatus, Dataset, Preview, Profile, Relationship, RelationshipResponse } from "./types";
import { PrepStudio } from "./PrepStudio";
import { MetricStudio } from "./MetricStudio";

const EChart = lazy(() => import("./EChart").then((module) => ({ default: module.EChart })));
const DashboardStudio = lazy(() => import("./DashboardStudio").then((module) => ({ default: module.DashboardStudio })));
const PipelineStudio = lazy(() => import("./PipelineStudio").then((module) => ({ default: module.PipelineStudio })));
const LolStudio = lazy(() => import("./LolStudio").then((module) => ({ default: module.LolStudio })));
const SourceStudio = lazy(() => import("./SourceStudio").then((module) => ({ default: module.SourceStudio })));
const ModelStudio = lazy(() => import("./ModelStudio").then((module) => ({ default: module.ModelStudio })));
const LoginScreen = lazy(() => import("./LoginScreen").then((module) => ({ default: module.LoginScreen })));
const SharedDashboard = lazy(() => import("./SharedDashboard").then((module) => ({ default: module.SharedDashboard })));

function LoadingPanel() {
  return <div className="recommend-placeholder">화면 모듈을 불러오는 중입니다…</div>;
}

const number = new Intl.NumberFormat("ko-KR");

function sampleOption(preview: Preview | null, relation: Relationship | null, selected: string): EChartsCoreOption {
  const empty: EChartsCoreOption = { xAxis: { type: "category", data: [] }, yAxis: {}, series: [] };
  if (!preview || !relation) return empty;
  const rows = preview.rows.slice(0, 80);
  const candidate = relation.column;
  const common = { animationDuration: 500, grid: { left: 48, right: 20, top: 34, bottom: 44 }, tooltip: { trigger: "item" as const }, textStyle: { fontFamily: "Inter, Pretendard, sans-serif" } };
  if (relation.relation_type === "numeric_numeric") {
    return { ...common, xAxis: { type: "value", name: selected }, yAxis: { type: "value", name: candidate }, series: [{ type: "scatter", symbolSize: 8, itemStyle: { color: "#36c99f" }, data: rows.map((row) => [Number(row[selected]), Number(row[candidate])]) }] };
  }
  if (relation.relation_type === "categorical_categorical") {
    const xLabels = [...new Set(rows.map((row) => String(row[selected])))].slice(0, 12);
    const yLabels = [...new Set(rows.map((row) => String(row[candidate])))].slice(0, 12);
    const counts = new Map<string, number>();
    for (const row of rows) {
      const key = `${String(row[selected])}\u0000${String(row[candidate])}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const data = xLabels.flatMap((x, xi) => yLabels.map((y, yi) => [xi, yi, counts.get(`${x}\u0000${y}`) ?? 0]));
    return { ...common, tooltip: { position: "top" }, xAxis: { type: "category", data: xLabels }, yAxis: { type: "category", data: yLabels }, visualMap: { min: 0, max: Math.max(...data.map((item) => Number(item[2])), 1), calculable: false, orient: "horizontal", left: "center", bottom: 0, inRange: { color: ["#eef4ff", "#2864dc"] } }, series: [{ type: "heatmap", data }] } as EChartsCoreOption;
  }
  if (relation.relation_type === "datetime_numeric") {
    const dateColumn = String(relation.chart_spec.x);
    const valueColumn = String(relation.chart_spec.y);
    const ordered = rows.map((row) => [String(row[dateColumn]), Number(row[valueColumn])] as [string, number]).filter((item) => Number.isFinite(item[1])).sort((a, b) => a[0].localeCompare(b[0]));
    return { ...common, tooltip: { trigger: "axis" }, xAxis: { type: "category", data: ordered.map((item) => item[0]), axisLabel: { hideOverlap: true } }, yAxis: { type: "value" }, dataZoom: [{ type: "inside" }, { type: "slider", height: 14 }], series: [{ type: "line", showSymbol: false, smooth: true, lineStyle: { color: "#36a889" }, areaStyle: { color: "rgba(54,168,137,.12)" }, data: ordered.map((item) => item[1]) }] } as EChartsCoreOption;
  }
  const categoryColumn = String(relation.chart_spec.category ?? selected);
  const valueColumn = String(relation.chart_spec.value ?? candidate);
  const grouped = new Map<string, number[]>();
  for (const row of rows) {
    const key = String(row[categoryColumn]);
    const value = Number(row[valueColumn]);
    if (Number.isFinite(value)) grouped.set(key, [...(grouped.get(key) ?? []), value]);
  }
  const labels = [...grouped.keys()].slice(0, 12);
  const values = labels.map((label) => {
    const bucket = grouped.get(label) ?? [];
    return bucket.reduce((a, b) => a + b, 0) / Math.max(bucket.length, 1);
  });
  return { ...common, xAxis: { type: "category", data: labels, axisLabel: { rotate: 22 } }, yAxis: { type: "value" }, series: [{ type: "bar", data: values, itemStyle: { color: "#5b8def", borderRadius: [5, 5, 0, 0] } }] } as EChartsCoreOption;
}

export default function App() {
  const [view, setView] = useState<"data" | "sources" | "models" | "prep" | "metrics" | "dashboard" | "pipeline" | "lol">("data");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [active, setActive] = useState<Dataset | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selectedColumn, setSelectedColumn] = useState("");
  const [relations, setRelations] = useState<RelationshipResponse | null>(null);
  const [selectedRelation, setSelectedRelation] = useState<Relationship | null>(null);
  const [entityKey, setEntityKey] = useState("");
  const [timeColumn, setTimeColumn] = useState("");
  const [analysisGrain, setAnalysisGrain] = useState<"" | "mean" | "latest">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [auth, setAuth] = useState<AuthStatus | null | undefined>(undefined);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await api.listDatasets();
      setDatasets(result);
      if (!active && result[0]) setActive(result[0]);
    } catch { setError("백엔드에 연결할 수 없습니다. API 서버 상태를 확인해 주세요."); }
  }, [active]);

  useEffect(() => { api.authStatus().then(setAuth).catch(() => setAuth(null)); }, []);
  useEffect(() => { if (auth) void refresh(); }, [auth]);
  useEffect(() => {
    if (!active) return;
    setBusy(true); setError(""); setRelations(null); setSelectedRelation(null);
    Promise.all([api.profile(active.id), api.preview(active.id)])
      .then(([p, rows]) => { setProfile(p); setPreview(rows); setSelectedColumn(p.columns.find((c) => c.semantic_type === "numeric" || c.semantic_type === "categorical")?.name ?? ""); })
      .catch((e: Error) => setError(e.message)).finally(() => setBusy(false));
  }, [active?.id]);

  async function upload(file?: File) {
    if (!file) return;
    setBusy(true); setError("");
    try { const created = await api.upload(file); await refresh(); setActive(created); }
    catch (e) { setError(e instanceof Error ? e.message : "업로드에 실패했습니다."); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function analyze() {
    if (!active || !selectedColumn) return;
    setBusy(true); setError("");
    try { const result = await api.relationships(active.id, selectedColumn, { entity_key: entityKey || null, time_column: timeColumn || null, analysis_grain: analysisGrain || null }); setRelations(result); setSelectedRelation(result.items[0] ?? null); }
    catch (e) { setError(e instanceof Error ? e.message : "관계 분석에 실패했습니다."); }
    finally { setBusy(false); }
  }

  const filtered = datasets.filter((d) => d.name.toLowerCase().includes(query.toLowerCase()));
  const chartOption = useMemo(() => sampleOption(preview, selectedRelation, selectedColumn), [preview, selectedRelation, selectedColumn]);
  const viewTitle = { data: active?.name ?? "새 데이터로 분석을 시작하세요", sources: "DB 데이터 소스", models: "분석 데이터 모델", prep: "전처리 레시피", metrics: "지표 정의", dashboard: "대시보드 편집기", pipeline: "파이프라인 작업", lol: "LoL 데이터 실험실" }[view];

  if (auth === undefined) return <main className="login-shell"><div className="login-card">세션을 확인하고 있습니다…</div></main>;
  if (auth === null) return <Suspense fallback={<LoadingPanel/>}><LoginScreen onLoggedIn={setAuth}/></Suspense>;
  const shareToken = new URLSearchParams(window.location.search).get("share");
  if (shareToken) return <div className="shell"><main><header><div><p>분석 작업공간</p><h1>공유 대시보드</h1></div></header><Suspense fallback={<LoadingPanel/>}><SharedDashboard token={shareToken} onClose={() => { window.history.replaceState({}, "", window.location.pathname); window.location.reload(); }}/></Suspense></main></div>;
  async function logout() { await api.logout(); setAuth(null); setDatasets([]); setActive(null); }
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><BarChart3 size={21}/></div><div><b>Data BI</b><span>WITH LoL LAB</span></div></div>
      <nav><button className={view === "data" ? "nav-active" : ""} onClick={() => setView("data")}><Database size={17}/> 데이터 허브</button><button className={view === "sources" ? "nav-active" : ""} onClick={() => setView("sources")}><Database size={17}/> DB 소스</button><button className={view === "models" ? "nav-active" : ""} onClick={() => setView("models")}><Boxes size={17}/> 데이터 모델</button><button className={view === "prep" ? "nav-active" : ""} onClick={() => setView("prep")}><Table2 size={17}/> 전처리 레시피</button><button className={view === "metrics" ? "nav-active" : ""} onClick={() => setView("metrics")}><Sigma size={17}/> 지표 정의</button><button className={view === "dashboard" ? "nav-active" : ""} onClick={() => setView("dashboard")}><BarChart3 size={17}/> 대시보드</button><button className={view === "pipeline" ? "nav-active" : ""} onClick={() => setView("pipeline")}><Activity size={17}/> 파이프라인</button><button className={view === "lol" ? "nav-active" : ""} onClick={() => setView("lol")}><Gamepad2 size={17}/> LoL 실험실</button></nav>
      <div className="side-heading"><span>데이터셋</span><b>{datasets.length}</b></div>
      <div className="search"><Search size={15}/><input aria-label="데이터셋 검색" placeholder="검색" value={query} onChange={(e) => setQuery(e.target.value)}/></div>
      <div className="dataset-list">{filtered.map((dataset) => <button key={dataset.id} className={active?.id === dataset.id ? "selected" : ""} onClick={() => setActive(dataset)}><span className="dataset-icon"><Table2 size={15}/></span><span><b>{dataset.name}</b><small>{number.format(dataset.row_count ?? 0)}행 · {dataset.column_count ?? 0}열</small></span></button>)}</div>
      <button className="upload" onClick={() => fileRef.current?.click()}><FileUp size={16}/> 파일 가져오기</button>
      <input ref={fileRef} hidden type="file" accept=".csv,.xlsx,.xls,.parquet" onChange={(e) => void upload(e.target.files?.[0])}/>
      <div className="sidebar-foot"><span className="online-dot"/> Local core <small>DuckDB · Parquet</small></div>
    </aside>

    <main>
      <header><div><p>분석 작업공간</p><h1>{viewTitle}</h1></div><div className="header-actions">{auth.enabled && <span className="status">{auth.user?.email} · {auth.user?.role}</span>}<span className="status"><i/> 로컬 전용</span><button className="primary" onClick={() => fileRef.current?.click()}><FileUp size={16}/> 업로드</button>{auth.enabled && <button onClick={() => void logout()}><LogOut size={16}/> 로그아웃</button>}</div></header>
      {error && <div className="error">{error}</div>}
      <Suspense fallback={<LoadingPanel/>}>{view === "sources" ? <SourceStudio onSynced={refresh}/> : view === "models" ? <ModelStudio datasets={datasets} onBuilt={refresh}/> : view === "prep" ? <PrepStudio dataset={active} datasets={datasets} profile={profile} onPublished={async () => { await refresh(); if (active) { const [p, rows] = await Promise.all([api.profile(active.id), api.preview(active.id)]); setProfile(p); setPreview(rows); } }}/> : view === "metrics" ? <MetricStudio dataset={active} profile={profile}/> : view === "dashboard" ? <DashboardStudio dataset={active} profile={profile} preview={preview}/> : view === "pipeline" ? <PipelineStudio dataset={active} profile={profile}/> : view === "lol" ? <LolStudio datasets={datasets} onDatasetsChanged={refresh}/> : !active ? <section className="empty"><div><FileUp size={30}/></div><h2>첫 데이터셋을 올려보세요</h2><p>CSV, Excel, Parquet 파일을 원자적 버전으로 저장하고 바로 탐색할 수 있습니다.</p><button className="primary" onClick={() => fileRef.current?.click()}>파일 선택</button></section> : <>
        <section className="kpis">
          <article><span>레코드</span><strong>{number.format(profile?.row_count ?? active.row_count ?? 0)}</strong><small><ArrowUpRight size={13}/> 게시 버전 기준</small></article>
          <article><span>컬럼</span><strong>{profile?.column_count ?? active.column_count ?? 0}</strong><small>{profile?.columns.filter((c) => c.semantic_type === "numeric").length ?? 0}개 수치형</small></article>
          <article><span>데이터 완성도</span><strong>{profile ? `${(100 - profile.columns.reduce((s, c) => s + c.null_ratio, 0) / Math.max(profile.column_count, 1) * 100).toFixed(1)}%` : "—"}</strong><small>전체 컬럼 평균</small></article>
          <article><span>현재 버전</span><strong className="version">v1</strong><small>원자적 게시 완료</small></article>
        </section>

        <section className="workspace-grid">
          <article className="panel relation-panel">
            <div className="panel-head"><div><p>AI 관계 추천</p><h2>기준 컬럼과 함께 볼 지표</h2></div><Sparkles size={19}/></div>
            <div className="control-row"><label>기준 컬럼<select value={selectedColumn} onChange={(e) => {setSelectedColumn(e.target.value); setRelations(null); setSelectedRelation(null);}}>{profile?.columns.filter((c) => !["identifier", "text"].includes(c.semantic_type)).map((c) => <option key={c.name}>{c.name}</option>)}</select></label><button className="primary" disabled={busy || !selectedColumn} onClick={() => void analyze()}>{busy ? <LoaderCircle className="spin" size={16}/> : <Sparkles size={16}/>} 관계 찾기</button></div>
            <div className="control-row relation-grain"><label>반복 개체 키<select value={entityKey} onChange={(event) => { setEntityKey(event.target.value); if (!event.target.value) { setTimeColumn(""); setAnalysisGrain(""); } }}><option value="">행 단위(기본)</option>{profile?.columns.filter((c) => c.semantic_type === "identifier" || c.unique_count > 1).map((c) => <option key={c.name}>{c.name}</option>)}</select></label><label>시간 컬럼<select value={timeColumn} disabled={!entityKey} onChange={(event) => setTimeColumn(event.target.value)}><option value="">선택</option>{profile?.columns.filter((c) => c.semantic_type === "datetime" || c.name.toLowerCase().includes("minute") || c.name.toLowerCase().includes("time")).map((c) => <option key={c.name}>{c.name}</option>)}</select></label><label>분석 단위<select value={analysisGrain} disabled={!entityKey} onChange={(event) => setAnalysisGrain(event.target.value as "" | "mean" | "latest")}><option value="">선택</option><option value="latest">마지막 시점</option><option value="mean">개체별 평균</option></select></label></div>
            {entityKey && <p className="insight">반복 측정 데이터는 개체별 분석 단위를 선택해야 합니다. 마지막 시점은 시간 컬럼도 필요합니다.</p>}
            {!relations ? <div className="recommend-placeholder"><Link2 size={24}/><p>컬럼을 선택하면 통계적 관계가 높은 다른 컬럼을 선제적으로 제안합니다.</p><small>Spearman · Cramér’s V · η² 기반</small></div> : <div className="recommend-list">{relations.items.map((item, index) => <button key={item.column} className={selectedRelation?.column === item.column ? "active" : ""} onClick={() => setSelectedRelation(item)}><span className="rank">{index + 1}</span><span className="recommend-title"><b>{item.column}</b><small>{item.method} · n={number.format(item.sample_size)}</small></span><strong>{Math.abs(item.score).toFixed(3)}</strong></button>)}</div>}
          </article>
          <article className="panel chart-panel">
            <div className="panel-head"><div><p>관계 미리보기</p><h2>{selectedRelation ? `${selectedColumn} × ${selectedRelation.column}` : "추천 결과를 선택하세요"}</h2></div>{selectedRelation && <span className="method">{selectedRelation.method}</span>}</div>
            {selectedRelation ? <><EChart option={chartOption}/><p className="insight">{selectedRelation.reason}</p></> : <div className="chart-empty"><BarChart3 size={30}/><span>추천 관계의 차트가 이곳에 표시됩니다.</span></div>}
          </article>
        </section>

        <section className="panel table-panel"><div className="panel-head"><div><p>데이터 미리보기</p><h2>게시된 원본 데이터</h2></div><span className="method">최대 100행</span></div><div className="table-wrap"><table><thead><tr>{preview?.columns.map((col) => <th key={col}>{col}</th>)}</tr></thead><tbody>{preview?.rows.slice(0, 12).map((row, i) => <tr key={i}>{preview.columns.map((col) => <td key={col}>{String(row[col] ?? "—")}</td>)}</tr>)}</tbody></table></div></section>
      </>}</Suspense>
    </main>
  </div>;
}
