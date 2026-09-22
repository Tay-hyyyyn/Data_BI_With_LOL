import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ToastProvider } from "../components/Toast";
import { DatasetProvider } from "./DatasetContext";

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1 } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <DatasetProvider>{children}</DatasetProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
