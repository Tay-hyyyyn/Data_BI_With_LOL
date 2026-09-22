import { createBrowserRouter } from "react-router-dom";
import { DataHubPage } from "../features/datasets/DataHubPage";
import { DashboardStudio } from "../features/dashboards/DashboardStudio";
import { LolStudio } from "../features/lol/LolStudio";
import { MetricStudio } from "../features/metrics/MetricStudio";
import { PipelineStudio } from "../features/pipelines/PipelineStudio";
import { PrepStudio } from "../features/prep/PrepStudio";
import { AppLayout } from "./AppLayout";

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <DataHubPage /> },
      { path: "/prep", element: <PrepStudio /> },
      { path: "/metrics", element: <MetricStudio /> },
      { path: "/dashboards", element: <DashboardStudio /> },
      { path: "/pipelines", element: <PipelineStudio /> },
      { path: "/lol", element: <LolStudio /> },
    ],
  },
]);
