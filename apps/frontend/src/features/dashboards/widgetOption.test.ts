import type { EChartsCoreOption } from "echarts/core";
import { describe, expect, it } from "vitest";
import { buildWidgetOption } from "./widgetOption";

// `EChartsCoreOption["series"]` resolves to an overly generic union that TS can't index cleanly;
// the shape at runtime is always the array literal `buildWidgetOption` builds.
function seriesOf(option: EChartsCoreOption): Array<{ name?: string; data?: unknown[] }> {
  return option.series as never;
}

describe("buildWidgetOption", () => {
  it("builds one bar series with no legend when there is a single series", () => {
    const option = buildWidgetOption("bar", [
      { category: "search", value: 10 },
      { category: "social", value: 20 },
    ]);
    expect(option.xAxis).toMatchObject({ data: ["search", "social"] });
    expect(option.legend).toBeUndefined();
    const series = seriesOf(option);
    expect(series).toHaveLength(1);
    expect(series[0]).toMatchObject({ type: "bar", data: [10, 20] });
  });

  it("builds one series per distinct `series` value and shows a legend", () => {
    const option = buildWidgetOption("line", [
      { category: 10, series: "16.17", value: 3000 },
      { category: 10, series: "16.18", value: 3200 },
      { category: 15, series: "16.17", value: 5000 },
    ]);
    expect(option.legend).toMatchObject({ data: ["16.17", "16.18"] });
    const series = seriesOf(option);
    expect(series).toHaveLength(2);
    // Missing (category, series) combinations are null, not dropped, so both series keep the same length.
    expect(series[1]).toMatchObject({ name: "16.18", data: [3200, null] });
  });

  it("falls back to positional labels and a synthetic '전체' series when rows carry none", () => {
    const option = buildWidgetOption("kpi", [{ value: 42 }]);
    expect(option.xAxis).toMatchObject({ data: ["1"] });
    expect(seriesOf(option)[0]).toMatchObject({ name: "전체", data: [42] });
  });
});
