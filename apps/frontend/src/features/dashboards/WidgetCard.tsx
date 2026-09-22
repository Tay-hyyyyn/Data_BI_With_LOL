import type { EChartsCoreOption } from "echarts/core";
import { GripVertical, Trash2 } from "lucide-react";
import { useMemo } from "react";
import type { DashboardWidget, DatasetChartRequest, DatasetQuery } from "../../api/types";
import { EChart } from "../../components/EChart";
import { errorMessage } from "../../lib/apiClient";
import { formatDecimal } from "../../lib/format";
import { useDatasetChart, useDatasetQuery } from "../../lib/queries";
import { buildWidgetOption, type Row } from "./widgetOption";

const ADVANCED_TYPES: DashboardWidget["type"][] = ["histogram", "scatter", "boxplot", "heatmap"];
const AGGREGATION_LABEL: Record<string, string> = {
  sum: "전체 합계",
  mean: "평균",
  count: "행 수",
  min: "최솟값",
  max: "최댓값",
};

export function WidgetCard({
  datasetId,
  widget,
  filter,
  onRemove,
  ...drag
}: {
  datasetId: string;
  widget: DashboardWidget;
  filter: { column: string; value: string } | null;
  onRemove: () => void;
  draggable: boolean;
  onDragStart: () => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: () => void;
}) {
  const isAdvanced = ADVANCED_TYPES.includes(widget.type);
  const filters = filter ? [{ ...filter, operator: "eq" as const }] : [];

  // `bins`/`sample_limit`/`seed`/`aggregation`/`limit` all have server-side defaults (see
  // `DatasetChartRequest`/`DatasetQuery` in schemas/query.py); the generated type still marks them
  // required, so the omission here is intentional, not a typing gap.
  const chartPayload: DatasetChartRequest | null = isAdvanced
    ? ({
        chart_type: widget.type as DatasetChartRequest["chart_type"],
        x: widget.column,
        y: widget.secondary || null,
        group: widget.dimension || null,
        filters,
      } as DatasetChartRequest)
    : null;
  const queryPayload: DatasetQuery | null = !isAdvanced
    ? ({
        measure: widget.column,
        aggregation: widget.aggregation || "sum",
        dimension: widget.dimension || null,
        series: widget.series || null,
        filters,
      } as DatasetQuery)
    : null;

  const chart = useDatasetChart(datasetId, chartPayload);
  const query = useDatasetQuery(datasetId, queryPayload);

  // `DatasetQueryResult.rows` is `list[dict[str, Any]]` on the backend, so the generated type is
  // untyped per-row; every row this endpoint actually returns has at least `value` (see
  // `services/bi/query.py:query_dataset`).
  const queryRows = query.data?.rows;
  const rows = useMemo(() => (queryRows ?? []) as Row[], [queryRows]);
  const option = useMemo(() => buildWidgetOption(widget.type, rows), [widget.type, rows]);
  const total = rows[0]?.value ?? 0;
  const error = isAdvanced ? chart.error : query.error;
  const label = AGGREGATION_LABEL[widget.aggregation || "sum"];

  return (
    <article className="dashboard-widget" {...drag}>
      <div className="widget-head">
        <GripVertical size={17} />
        <b>{widget.title}</b>
        <button aria-label={`${widget.title} 삭제`} onClick={onRemove}>
          <Trash2 size={15} />
        </button>
      </div>
      {error ? (
        <div className="toast toast-error">{errorMessage(error, "집계 실패")}</div>
      ) : widget.type === "kpi" ? (
        <div className="widget-kpi">
          <span>{label}</span>
          <strong>{formatDecimal(total)}</strong>
          <small>게시 버전 전체 행 기준</small>
        </div>
      ) : (
        <EChart
          option={
            isAdvanced
              ? ((chart.data?.chart_spec as unknown as EChartsCoreOption) ?? option)
              : option
          }
        />
      )}
    </article>
  );
}
