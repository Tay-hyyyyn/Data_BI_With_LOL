import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Dataset } from "../api/types";
import { useDatasets } from "../lib/queries";

type DatasetContextValue = { activeId: string | undefined; setActiveId: (id: string) => void };

const DatasetContext = createContext<DatasetContextValue | null>(null);

/** Holds which dataset is selected in the sidebar. Lives above the router so every route shares it. */
export function DatasetProvider({ children }: { children: ReactNode }) {
  const [activeId, setActiveId] = useState<string | undefined>(undefined);
  const value = useMemo(() => ({ activeId, setActiveId }), [activeId]);
  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>;
}

/** The active dataset, defaulting to the first one once the list loads (mirrors the old `App.tsx` behavior). */
export function useActiveDataset(): {
  active: Dataset | null;
  datasets: Dataset[];
  setActiveId: (id: string) => void;
  isLoading: boolean;
} {
  const context = useContext(DatasetContext);
  if (!context)
    throw new Error("useActiveDataset은 DatasetProvider 내부에서만 사용할 수 있습니다.");
  const { data, isLoading } = useDatasets();
  const datasets = data ?? [];
  const active = datasets.find((dataset) => dataset.id === context.activeId) ?? datasets[0] ?? null;
  return { active, datasets, setActiveId: context.setActiveId, isLoading };
}
