import type { EChartsCoreOption } from "echarts/core";
import type { DashboardWidget } from "../../api/types";

export type Row = { category?: unknown; series?: unknown; value: number | null };

const SERIES_COLORS = ["#3977e8", "#36a889", "#f09b4d", "#9364d9", "#d95f8d"];

/** Builds a bar/line ECharts option from `query_dataset` rows. Pure — unit-tested in isolation. */
export function buildWidgetOption(
  widgetType: DashboardWidget["type"],
  rows: Row[],
): EChartsCoreOption {
  // Label with the same fallback used when *looking up* a row below, so a categoryless row
  // (a single aggregate value with no grouping) still finds its own bar instead of an axis
  // label with nothing plotted under it.
  const categoryLabel = (row: Row, index: number) => String(row.category ?? index + 1);
  const categories = [...new Set(rows.map(categoryLabel))];
  const seriesNames = [...new Set(rows.map((row) => String(row.series ?? "전체")))];
  return {
    grid: { left: 45, right: 12, top: seriesNames.length > 1 ? 32 : 12, bottom: 28 },
    legend: seriesNames.length > 1 ? { data: seriesNames } : undefined,
    xAxis: { type: "category", data: categories },
    yAxis: { type: "value" },
    series: seriesNames.map((name, index) => ({
      name,
      type: widgetType === "line" ? "line" : "bar",
      showSymbol: false,
      data: categories.map(
        (category) =>
          rows.find(
            (row, rowIndex) =>
              categoryLabel(row, rowIndex) === category && String(row.series ?? "전체") === name,
          )?.value ?? null,
      ),
      itemStyle: { color: SERIES_COLORS[index % SERIES_COLORS.length] },
    })),
  } as EChartsCoreOption;
}
