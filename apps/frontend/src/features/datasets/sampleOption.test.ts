import type { EChartsCoreOption } from "echarts/core";
import { describe, expect, it } from "vitest";
import type { Preview, Relationship } from "../../api/types";
import { sampleOption } from "./sampleOption";

const preview: Preview = {
  columns: ["x", "y"],
  rows: [
    { x: 1, y: 2 },
    { x: 3, y: 4 },
  ],
};

function relationship(overrides: Partial<Relationship>): Relationship {
  return {
    column: "y",
    relation_type: "numeric_numeric",
    method: "spearman",
    score: 0.5,
    direction: "positive",
    sample_size: 2,
    null_ratio: 0,
    reason: "",
    chart_spec: {},
    ...overrides,
  };
}

// See the matching helper in widgetOption.test.ts for why this cast is needed.
function firstSeries(option: EChartsCoreOption): { type?: string; data?: unknown[] } {
  return (option.series as never as Array<{ type?: string; data?: unknown[] }>)[0];
}

describe("sampleOption", () => {
  it("returns an empty option when there is no preview or relation", () => {
    expect(sampleOption(null, null, "x").series).toEqual([]);
  });

  it("plots a scatter for a numeric x numeric relation", () => {
    const option = sampleOption(preview, relationship({ relation_type: "numeric_numeric" }), "x");
    expect(firstSeries(option)).toMatchObject({
      type: "scatter",
      data: [
        [1, 2],
        [3, 4],
      ],
    });
  });

  it("plots a bar chart grouped by category for the categorical fallback branch", () => {
    const grouped: Preview = {
      columns: ["channel", "revenue"],
      rows: [
        { channel: "a", revenue: 10 },
        { channel: "a", revenue: 20 },
        { channel: "b", revenue: 5 },
      ],
    };
    const option = sampleOption(
      grouped,
      relationship({
        relation_type: "categorical_numeric",
        chart_spec: { category: "channel", value: "revenue" },
      }),
      "channel",
    );
    expect(option.xAxis).toMatchObject({ data: ["a", "b"] });
    expect(firstSeries(option)).toMatchObject({ type: "bar", data: [15, 5] });
  });
});
