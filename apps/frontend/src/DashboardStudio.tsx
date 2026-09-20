import { useEffect, useMemo, useState } from "react";
import { BarChart3, GripVertical, Plus, Save, Share2, Trash2 } from "lucide-react";
import { api } from "./api";
import { EChart } from "./EChart";
import type { Dashboard, DashboardWidget, Dataset, Preview, Profile } from "./types";

type Widget = DashboardWidget;

export function DashboardStudio({ dataset, profile, preview }: { dataset: Dataset | null; profile: Profile | null; preview: Preview | null }) {
  const numeric = profile?.columns.filter((column) => column.semantic_type === "numeric") ?? [];
  const [name, setName] = useState("새 분석 대시보드");
  const [column, setColumn] = useState("");
  const [kind, setKind] = useState<Widget["type"]>("kpi");
  const [aggregation, setAggregation] = useState<NonNullable<Widget["aggregation"]>>("sum");
  const [dimension, setDimension] = useState("");
  const [series, setSeries] = useState("");
  const [secondary, setSecondary] = useState("");
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [saved, setSaved] = useState<Dashboard[]>([]);
  const [dashboardId, setDashboardId] = useState("");
  const [filterColumn, setFilterColumn] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [dragged, setDragged] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [shareUrl, setShareUrl] = useState("");
  const categorical = profile?.columns.filter((item) => item.semantic_type === "categorical") ?? [];
  const dimensions = profile?.columns.filter((item) => !["identifier", "text"].includes(item.semantic_type)) ?? [];
  const canCreateMarketingStarter = ["date", "channel", "spend", "impressions", "clicks", "conversions", "revenue", "roas"].every((name) => profile?.columns.some((column) => column.name === name));
  useEffect(() => { setColumn(numeric[0]?.name ?? ""); setSecondary(numeric[1]?.name ?? numeric[0]?.name ?? ""); setDimension(dimensions[0]?.name ?? ""); setSeries(categorical[0]?.name ?? ""); setFilterColumn(categorical[0]?.name ?? ""); }, [profile?.version_id]);
  useEffect(() => { api.listDashboards().then(setSaved).catch(() => setSaved([])); }, []);
  const filterValues = useMemo(() => filterColumn ? [...new Set(preview?.rows.map((row) => String(row[filterColumn])) ?? [])].slice(0, 50) : [], [preview, filterColumn]);
  const filteredRows = useMemo(() => filterColumn && filterValue ? (preview?.rows ?? []).filter((row) => String(row[filterColumn]) === filterValue) : preview?.rows ?? [], [preview, filterColumn, filterValue]);

  function add() {
    const primary = kind === "heatmap" ? dimension : column;
    if (!primary) return;
    const needsGroup = ["bar", "line", "boxplot"].includes(kind);
    setWidgets((current) => [...current, { id: crypto.randomUUID(), title: primary, type: kind, column: primary, aggregation, dimension: needsGroup ? dimension || undefined : undefined, series: ["bar", "line"].includes(kind) ? series || undefined : undefined, secondary: ["scatter", "heatmap"].includes(kind) ? secondary || undefined : undefined }]);
  }
  function drop(index: number) {
    if (dragged === null || dragged === index) return;
    setWidgets((current) => { const next = [...current]; const [item] = next.splice(dragged, 1); next.splice(index, 0, item); return next; });
    setDragged(null);
  }
  async function save() {
    setMessage("");
    const payload = { name, widgets: widgets.map((widget) => ({ ...widget, dataset_id: widget.dataset_id || dataset?.id })), filters: filterColumn ? [{ column: filterColumn, value: filterValue }] : [] };
    try { const result = dashboardId ? await api.updateDashboard(dashboardId, payload) : await api.saveDashboard(payload); setDashboardId(result.id); setSaved(await api.listDashboards()); setMessage("대시보드를 비공개로 저장했습니다."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "저장하지 못했습니다."); }
  }
  async function openSaved(id: string) {
    setDashboardId(id); setMessage("");
    if (!id) { setName("새 분석 대시보드"); setWidgets([]); return; }
    try {
      const dashboard = await api.getDashboard(id);
      setName(dashboard.name);
      setWidgets(dashboard.widgets.filter((item) => typeof item.id === "string" && typeof item.column === "string") as Widget[]);
      const filter = dashboard.filters[0];
      setFilterColumn(typeof filter?.column === "string" ? filter.column : "");
      setFilterValue(typeof filter?.value === "string" ? filter.value : "");
      setMessage("저장된 대시보드를 불러왔습니다.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "불러오지 못했습니다."); }
  }
  async function clone() {
    if (!dashboardId) return;
    try { const result = await api.cloneDashboard(dashboardId); setSaved(await api.listDashboards()); await openSaved(result.id); setMessage("대시보드 복사본을 만들었습니다."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "복제하지 못했습니다."); }
  }
  async function publish() {
    if (!dashboardId) return;
    try { const result = await api.publishDashboard(dashboardId, true); setSaved(await api.listDashboards()); setMessage(result.visibility === "published" ? "대시보드를 게시 상태로 전환했습니다." : "게시 상태를 변경했습니다."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "게시하지 못했습니다."); }
  }
  async function share() {
    if (!dashboardId) return;
    try {
      const share = await api.createDashboardShare(dashboardId);
      const url = `${window.location.origin}${window.location.pathname}?share=${encodeURIComponent(share.token)}`;
      setShareUrl(url);
      await navigator.clipboard?.writeText(url);
      setMessage("로그인 사용자 전용 읽기 링크를 만들고 클립보드에 복사했습니다.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "공유 링크를 만들지 못했습니다."); }
  }
  async function createMarketingStarter() {
    if (!dataset) return;
    try {
      const result = await api.createMarketingStarterDashboard(dataset.id);
      setSaved(await api.listDashboards());
      await openSaved(result.id);
      setMessage("마케팅 성과 시작 대시보드를 비공개로 만들었습니다.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "시작 대시보드를 만들지 못했습니다."); }
  }

  if (!dataset || !profile || !preview) return <section className="empty"><h2>먼저 데이터셋을 선택하세요</h2></section>;
  return <section className="studio">
    <div className="studio-toolbar"><div><p>대시보드 편집기</p><input aria-label="대시보드 이름" value={name} onChange={(event) => setName(event.target.value)}/><select className="saved-dashboard" aria-label="저장된 대시보드" value={dashboardId} onChange={(event) => void openSaved(event.target.value)}><option value="">새 대시보드</option>{saved.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><div className="widget-controls">{canCreateMarketingStarter && <button onClick={() => void createMarketingStarter()}>마케팅 시작 대시보드</button>}<select aria-label="위젯 유형" value={kind} onChange={(event) => { const next = event.target.value as Widget["type"]; setKind(next); setSecondary(next === "heatmap" ? categorical[1]?.name ?? categorical[0]?.name ?? "" : numeric[1]?.name ?? numeric[0]?.name ?? ""); }}><option value="kpi">KPI</option><option value="bar">막대 차트</option><option value="line">선 차트</option><option value="histogram">히스토그램</option><option value="scatter">산점도</option><option value="boxplot">박스플롯</option><option value="heatmap">히트맵</option></select>{kind !== "heatmap" && <select aria-label="지표 컬럼" value={column} onChange={(event) => setColumn(event.target.value)}>{numeric.map((item) => <option key={item.name}>{item.name}</option>)}</select>}{!["histogram", "scatter", "boxplot", "heatmap"].includes(kind) && <select aria-label="집계 방식" value={aggregation} onChange={(event) => setAggregation(event.target.value as NonNullable<Widget["aggregation"]>)}><option value="sum">합계</option><option value="mean">평균</option><option value="count">개수</option><option value="min">최솟값</option><option value="max">최댓값</option></select>}{["bar", "line", "boxplot", "heatmap"].includes(kind) && <select aria-label={kind === "heatmap" ? "첫 번째 범주 컬럼" : "그룹 컬럼"} value={dimension} onChange={(event) => setDimension(event.target.value)}><option value="">그룹 없음</option>{dimensions.map((item) => <option key={item.name}>{item.name}</option>)}</select>}{["bar", "line"].includes(kind) && <select aria-label="계열 컬럼" value={series} onChange={(event) => setSeries(event.target.value)}><option value="">계열 없음</option>{categorical.filter((item) => item.name !== dimension).map((item) => <option key={item.name}>{item.name}</option>)}</select>}{["scatter", "heatmap"].includes(kind) && <select aria-label="두 번째 컬럼" value={secondary} onChange={(event) => setSecondary(event.target.value)}>{(kind === "heatmap" ? categorical : numeric).map((item) => <option key={item.name}>{item.name}</option>)}</select>}<button onClick={add}><Plus size={16}/> 위젯 추가</button><button className="primary" onClick={() => void save()}><Save size={16}/> 저장</button>{dashboardId && <><button onClick={() => void clone()}>복제</button><button onClick={() => void publish()}>게시</button><button onClick={() => void share()}><Share2 size={16}/> 공유</button></>}</div></div>
    {message && <div className="notice">{message}</div>}{shareUrl && <div className="share-link"><input readOnly value={shareUrl}/><button onClick={() => void navigator.clipboard?.writeText(shareUrl)}>복사</button></div>}
    <div className="filter-bar"><b>공통 필터</b><select value={filterColumn} onChange={(event) => { setFilterColumn(event.target.value); setFilterValue(""); }}><option value="">사용 안 함</option>{categorical.map((item) => <option key={item.name}>{item.name}</option>)}</select><select value={filterValue} disabled={!filterColumn} onChange={(event) => setFilterValue(event.target.value)}><option value="">전체</option>{filterValues.map((item) => <option key={item}>{item}</option>)}</select><span>{filteredRows.length.toLocaleString()}행 적용</span></div>
    <div className="dashboard-grid">{widgets.length === 0 ? <div className="dashboard-empty"><BarChart3 size={32}/><b>오른쪽 위에서 첫 위젯을 추가하세요</b><span>카드를 끌어서 표시 순서를 바꿀 수 있습니다.</span></div> : widgets.map((widget, index) => <WidgetCard key={widget.id} datasetId={widget.dataset_id || dataset.id} widget={widget} filter={filterColumn && filterValue ? { column: filterColumn, value: filterValue } : null} draggable onDragStart={() => setDragged(index)} onDragOver={(event) => event.preventDefault()} onDrop={() => drop(index)} onRemove={() => setWidgets((current) => current.filter((item) => item.id !== widget.id))}/>)}</div>
  </section>;
}

export function WidgetCard({ datasetId, widget, filter, onRemove, readOnly = false, ...drag }: { datasetId: string; widget: Widget; filter: { column: string; value: string } | null; onRemove: () => void; readOnly?: boolean; draggable: boolean; onDragStart: () => void; onDragOver: (event: React.DragEvent) => void; onDrop: () => void }) {
  const [rows, setRows] = useState<Array<{ category?: unknown; series?: unknown; value: number | null }>>([]);
  const [chartSpec, setChartSpec] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const filters = filter ? [{ ...filter, operator: "eq" }] : [];
    const advanced = ["histogram", "scatter", "boxplot", "heatmap"].includes(widget.type);
    const request = advanced
      ? api.chartDataset(datasetId, { chart_type: widget.type, x: widget.column, y: widget.secondary || null, group: widget.dimension || null, filters })
      : api.queryDataset(datasetId, { measure: widget.column, aggregation: widget.aggregation || "sum", dimension: widget.dimension || null, series: widget.series || null, filters });
    request
      .then((result) => { if (active) { if ("chart_spec" in result) setChartSpec(result.chart_spec); else { setRows(result.rows); setChartSpec(null); } setError(""); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "집계 실패"); });
    return () => { active = false; };
  }, [datasetId, widget.column, widget.dimension, widget.series, widget.secondary, widget.type, filter?.column, filter?.value]);
  const total = rows[0]?.value ?? 0;
  const option = useMemo(() => {
    const categories = [...new Set(rows.map((row, index) => String(row.category ?? index + 1)))];
    const seriesNames = [...new Set(rows.map((row) => String(row.series ?? "전체")))];
    return { grid: { left: 45, right: 12, top: seriesNames.length > 1 ? 32 : 12, bottom: 28 }, legend: seriesNames.length > 1 ? { data: seriesNames } : undefined, xAxis: { type: "category" as const, data: categories }, yAxis: { type: "value" as const }, series: seriesNames.map((name, index) => ({ name, type: widget.type === "line" ? "line" as const : "bar" as const, showSymbol: false, data: categories.map((category) => rows.find((row) => String(row.category) === category && String(row.series ?? "전체") === name)?.value ?? null), itemStyle: { color: ["#3977e8", "#36a889", "#f09b4d", "#9364d9", "#d95f8d"][index % 5] } })) };
  }, [widget.type, rows]);
  const label = { sum: "전체 합계", mean: "평균", count: "행 수", min: "최솟값", max: "최댓값" }[widget.aggregation || "sum"];
  return <article className="dashboard-widget" {...drag}><div className="widget-head">{!readOnly && <GripVertical size={17}/>}<b>{widget.title}</b>{!readOnly && <button aria-label={`${widget.title} 삭제`} onClick={onRemove}><Trash2 size={15}/></button>}</div>{error ? <div className="notice">{error}</div> : widget.type === "kpi" ? <div className="widget-kpi"><span>{label}</span><strong>{new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(total)}</strong><small>게시 버전 전체 행 기준</small></div> : <EChart option={chartSpec ?? option}/>}</article>;
}
