import { BarChart3, Plus, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useActiveDataset } from "../../app/DatasetContext";
import { isDashboardWidget, type DashboardWidget } from "../../api/types";
import { useToast } from "../../components/Toast";
import { errorMessage } from "../../lib/apiClient";
import {
  useCloneDashboard,
  useDashboard,
  useDashboards,
  usePreview,
  useProfile,
  usePublishDashboard,
  useSaveDashboard,
  useUpdateDashboard,
} from "../../lib/queries";
import { WidgetCard } from "./WidgetCard";

type Widget = DashboardWidget;

export function DashboardStudio() {
  const { active } = useActiveDataset();
  const { data: profile } = useProfile(active?.id);
  const { data: preview } = usePreview(active?.id, 100);
  const { data: saved = [] } = useDashboards();
  const { notify } = useToast();

  const numeric = profile?.columns.filter((column) => column.semantic_type === "numeric") ?? [];
  const categorical = profile?.columns.filter((item) => item.semantic_type === "categorical") ?? [];
  const dimensions =
    profile?.columns.filter((item) => !["identifier", "text"].includes(item.semantic_type)) ?? [];

  const [name, setName] = useState("새 분석 대시보드");
  const [column, setColumn] = useState("");
  const [kind, setKind] = useState<Widget["type"]>("kpi");
  const [aggregation, setAggregation] = useState<NonNullable<Widget["aggregation"]>>("sum");
  const [dimension, setDimension] = useState("");
  const [series, setSeries] = useState("");
  const [secondary, setSecondary] = useState("");
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [dashboardId, setDashboardId] = useState("");
  const [filterColumn, setFilterColumn] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [dragged, setDragged] = useState<number | null>(null);

  const { data: openedDashboard } = useDashboard(dashboardId || undefined);
  useEffect(() => {
    setColumn(numeric[0]?.name ?? "");
    setSecondary(numeric[1]?.name ?? numeric[0]?.name ?? "");
    setDimension(dimensions[0]?.name ?? "");
    setSeries(categorical[0]?.name ?? "");
    setFilterColumn(categorical[0]?.name ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset defaults only when the dataset version changes
  }, [profile?.version_id]);
  useEffect(() => {
    if (!openedDashboard) return;
    setName(openedDashboard.name);
    setWidgets(openedDashboard.widgets.filter(isDashboardWidget));
    const filter = openedDashboard.filters[0];
    setFilterColumn(typeof filter?.column === "string" ? filter.column : "");
    setFilterValue(typeof filter?.value === "string" ? filter.value : "");
  }, [openedDashboard]);

  const filterValues = useMemo(
    () =>
      filterColumn
        ? [...new Set(preview?.rows.map((row) => String(row[filterColumn])) ?? [])].slice(0, 50)
        : [],
    [preview, filterColumn],
  );
  const filteredRowCount = useMemo(
    () =>
      filterColumn && filterValue
        ? (preview?.rows ?? []).filter((row) => String(row[filterColumn]) === filterValue).length
        : (preview?.rows.length ?? 0),
    [preview, filterColumn, filterValue],
  );

  const save = useSaveDashboard();
  const update = useUpdateDashboard();
  const clone = useCloneDashboard();
  const publish = usePublishDashboard();

  function addWidget() {
    const primary = kind === "heatmap" ? dimension : column;
    if (!primary) return;
    const needsGroup = ["bar", "line", "boxplot"].includes(kind);
    setWidgets((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        title: primary,
        type: kind,
        column: primary,
        aggregation,
        dimension: needsGroup ? dimension || undefined : undefined,
        series: ["bar", "line"].includes(kind) ? series || undefined : undefined,
        secondary: ["scatter", "heatmap"].includes(kind) ? secondary || undefined : undefined,
      },
    ]);
  }

  function drop(index: number) {
    if (dragged === null || dragged === index) return;
    setWidgets((current) => {
      const next = [...current];
      const [item] = next.splice(dragged, 1);
      next.splice(index, 0, item);
      return next;
    });
    setDragged(null);
  }

  async function handleSave() {
    const payload = {
      name,
      widgets: widgets.map((widget) => ({
        ...widget,
        dataset_id: widget.dataset_id || active?.id,
      })),
      filters: filterColumn ? [{ column: filterColumn, value: filterValue }] : [],
    };
    try {
      const result = dashboardId
        ? await update.mutateAsync({ id: dashboardId, payload })
        : await save.mutateAsync(payload);
      setDashboardId(result.id);
      notify("대시보드를 비공개로 저장했습니다.");
    } catch (error) {
      notify(errorMessage(error, "저장하지 못했습니다."), "error");
    }
  }

  function openSaved(id: string) {
    setDashboardId(id);
    if (!id) {
      setName("새 분석 대시보드");
      setWidgets([]);
    }
  }

  async function handleClone() {
    if (!dashboardId) return;
    try {
      const result = await clone.mutateAsync(dashboardId);
      openSaved(result.id);
      notify("대시보드 복사본을 만들었습니다.");
    } catch (error) {
      notify(errorMessage(error, "복제하지 못했습니다."), "error");
    }
  }

  async function handlePublish() {
    if (!dashboardId) return;
    try {
      const result = await publish.mutateAsync({ id: dashboardId, published: true });
      notify(
        result.visibility === "published"
          ? "대시보드를 게시 상태로 전환했습니다."
          : "게시 상태를 변경했습니다.",
      );
    } catch (error) {
      notify(errorMessage(error, "게시하지 못했습니다."), "error");
    }
  }

  if (!active || !profile || !preview)
    return (
      <section className="empty">
        <h2>먼저 데이터셋을 선택하세요</h2>
      </section>
    );

  return (
    <section className="studio">
      <div className="studio-toolbar">
        <div>
          <p>대시보드 편집기</p>
          <input
            aria-label="대시보드 이름"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <select
            className="saved-dashboard"
            aria-label="저장된 대시보드"
            value={dashboardId}
            onChange={(event) => openSaved(event.target.value)}
          >
            <option value="">새 대시보드</option>
            {saved.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className="widget-controls">
          <select
            aria-label="위젯 유형"
            value={kind}
            onChange={(event) => {
              const next = event.target.value as Widget["type"];
              setKind(next);
              setSecondary(
                next === "heatmap"
                  ? (categorical[1]?.name ?? categorical[0]?.name ?? "")
                  : (numeric[1]?.name ?? numeric[0]?.name ?? ""),
              );
            }}
          >
            <option value="kpi">KPI</option>
            <option value="bar">막대 차트</option>
            <option value="line">선 차트</option>
            <option value="histogram">히스토그램</option>
            <option value="scatter">산점도</option>
            <option value="boxplot">박스플롯</option>
            <option value="heatmap">히트맵</option>
          </select>
          {kind !== "heatmap" && (
            <select
              aria-label="지표 컬럼"
              value={column}
              onChange={(event) => setColumn(event.target.value)}
            >
              {numeric.map((item) => (
                <option key={item.name}>{item.name}</option>
              ))}
            </select>
          )}
          {!["histogram", "scatter", "boxplot", "heatmap"].includes(kind) && (
            <select
              aria-label="집계 방식"
              value={aggregation}
              onChange={(event) =>
                setAggregation(event.target.value as NonNullable<Widget["aggregation"]>)
              }
            >
              <option value="sum">합계</option>
              <option value="mean">평균</option>
              <option value="count">개수</option>
              <option value="min">최솟값</option>
              <option value="max">최댓값</option>
            </select>
          )}
          {["bar", "line", "boxplot", "heatmap"].includes(kind) && (
            <select
              aria-label={kind === "heatmap" ? "첫 번째 범주 컬럼" : "그룹 컬럼"}
              value={dimension}
              onChange={(event) => setDimension(event.target.value)}
            >
              <option value="">그룹 없음</option>
              {dimensions.map((item) => (
                <option key={item.name}>{item.name}</option>
              ))}
            </select>
          )}
          {["bar", "line"].includes(kind) && (
            <select
              aria-label="계열 컬럼"
              value={series}
              onChange={(event) => setSeries(event.target.value)}
            >
              <option value="">계열 없음</option>
              {categorical
                .filter((item) => item.name !== dimension)
                .map((item) => (
                  <option key={item.name}>{item.name}</option>
                ))}
            </select>
          )}
          {["scatter", "heatmap"].includes(kind) && (
            <select
              aria-label="두 번째 컬럼"
              value={secondary}
              onChange={(event) => setSecondary(event.target.value)}
            >
              {(kind === "heatmap" ? categorical : numeric).map((item) => (
                <option key={item.name}>{item.name}</option>
              ))}
            </select>
          )}
          <button onClick={addWidget}>
            <Plus size={16} /> 위젯 추가
          </button>
          <button className="primary" onClick={() => void handleSave()}>
            <Save size={16} /> 저장
          </button>
          {dashboardId && (
            <>
              <button onClick={() => void handleClone()}>복제</button>
              <button onClick={() => void handlePublish()}>게시</button>
            </>
          )}
        </div>
      </div>
      <div className="filter-bar">
        <b>공통 필터</b>
        <select
          value={filterColumn}
          onChange={(event) => {
            setFilterColumn(event.target.value);
            setFilterValue("");
          }}
        >
          <option value="">사용 안 함</option>
          {categorical.map((item) => (
            <option key={item.name}>{item.name}</option>
          ))}
        </select>
        <select
          value={filterValue}
          disabled={!filterColumn}
          onChange={(event) => setFilterValue(event.target.value)}
        >
          <option value="">전체</option>
          {filterValues.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <span>{filteredRowCount.toLocaleString()}행 적용</span>
      </div>
      <div className="dashboard-grid">
        {widgets.length === 0 ? (
          <div className="dashboard-empty">
            <BarChart3 size={32} />
            <b>오른쪽 위에서 첫 위젯을 추가하세요</b>
            <span>카드를 끌어서 표시 순서를 바꿀 수 있습니다.</span>
          </div>
        ) : (
          widgets.map((widget, index) => (
            <WidgetCard
              key={widget.id}
              datasetId={widget.dataset_id || active.id}
              widget={widget}
              filter={
                filterColumn && filterValue ? { column: filterColumn, value: filterValue } : null
              }
              draggable
              onDragStart={() => setDragged(index)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => drop(index)}
              onRemove={() =>
                setWidgets((current) => current.filter((item) => item.id !== widget.id))
              }
            />
          ))
        )}
      </div>
    </section>
  );
}
