import { init, type ECharts, type EChartsCoreOption } from "echarts/core";
import { useEffect, useRef } from "react";
import "./echarts-registry";

/**
 * Mounts one ECharts instance for the component's lifetime and calls `setOption` on it when
 * `option` changes, instead of disposing and recreating the canvas every time — which lost
 * animation, tooltip state and dataZoom position on every filter change.
 */
export function EChart({ option }: { option: EChartsCoreOption }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = init(containerRef.current);
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true });
  }, [option]);

  return <div className="chart-canvas" ref={containerRef} />;
}
