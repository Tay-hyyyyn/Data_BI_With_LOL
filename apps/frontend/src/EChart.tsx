import { useEffect, useRef } from "react";
import { init, use, type EChartsCoreOption } from "echarts/core";
import { BarChart, BoxplotChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

use([
  BarChart,
  BoxplotChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export function EChart({ option }: { option: EChartsCoreOption }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = init(ref.current);
    chart.setOption(option);
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [option]);
  return <div className="chart-canvas" ref={ref} />;
}
