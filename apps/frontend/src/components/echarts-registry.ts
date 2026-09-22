/**
 * The single `use([...])` registration point for ECharts. Every chart type and component the app
 * renders must be listed here — this is where `BoxplotChart` and `LegendComponent` were missing
 * (boxplot widgets rendered nothing; multi-series charts had no legend).
 */
import { BarChart, BoxplotChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
// Aliased: eslint's react-hooks plugin treats any top-level call named `use*` as a hook call.
import { use as registerEchartsModules } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

registerEchartsModules([
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
