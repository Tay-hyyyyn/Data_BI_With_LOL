import { useEffect, useState } from "react";
import { ArrowLeft, Eye } from "lucide-react";
import { api } from "./api";
import { WidgetCard } from "./DashboardStudio";
import type { Dashboard, DashboardWidget } from "./types";

export function SharedDashboard({ token, onClose }: { token: string; onClose: () => void }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.getSharedDashboard(token).then(setDashboard).catch((reason) => setError(reason instanceof Error ? reason.message : "공유 대시보드를 불러오지 못했습니다.")); }, [token]);
  if (error) return <section className="empty"><h2>{error}</h2><button onClick={onClose}>작업공간으로 돌아가기</button></section>;
  if (!dashboard) return <section className="empty"><h2>공유 대시보드를 불러오는 중입니다…</h2></section>;
  const filter = dashboard.filters[0];
  return <section className="studio shared-dashboard"><div className="studio-toolbar"><div><p><Eye size={15}/> 로그인 사용자 전용 · 읽기 전용</p><h2>{dashboard.name}</h2></div><button onClick={onClose}><ArrowLeft size={16}/> 작업공간</button></div><div className="notice">이 링크로는 대시보드를 조회만 할 수 있습니다. 편집과 데이터 변경은 허용되지 않습니다.</div><div className="dashboard-grid">{dashboard.widgets.map((raw) => { const widget = raw as unknown as DashboardWidget; if (!widget.id || !widget.dataset_id || !widget.column) return null; return <WidgetCard key={widget.id} datasetId={widget.dataset_id} widget={widget} filter={typeof filter?.column === "string" && typeof filter?.value === "string" ? { column: filter.column, value: filter.value } : null} readOnly draggable={false} onRemove={() => undefined} onDragStart={() => undefined} onDragOver={() => undefined} onDrop={() => undefined}/>; })}</div></section>;
}
