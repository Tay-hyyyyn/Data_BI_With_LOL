import {
  Activity,
  BarChart3,
  Database,
  FileUp,
  Gamepad2,
  Search,
  Sigma,
  Table2,
} from "lucide-react";
import { useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useToast } from "../components/Toast";
import { errorMessage } from "../lib/apiClient";
import { formatInteger } from "../lib/format";
import { useUploadDataset } from "../lib/queries";
import { useActiveDataset } from "./DatasetContext";

const NAV_ITEMS = [
  { to: "/", label: "데이터 허브", icon: Database },
  { to: "/prep", label: "전처리 레시피", icon: Table2 },
  { to: "/metrics", label: "지표 정의", icon: Sigma },
  { to: "/dashboards", label: "대시보드", icon: BarChart3 },
  { to: "/pipelines", label: "파이프라인", icon: Activity },
  { to: "/lol", label: "LoL 실험실", icon: Gamepad2 },
];

const PAGE_TITLES: Record<string, string> = {
  "/prep": "전처리 레시피",
  "/metrics": "지표 정의",
  "/dashboards": "대시보드 편집기",
  "/pipelines": "파이프라인 작업",
  "/lol": "LoL 데이터 실험실",
};

export function AppLayout() {
  const { active, datasets, setActiveId } = useActiveDataset();
  const location = useLocation();
  const [query, setQuery] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useUploadDataset();
  const { notify } = useToast();

  async function handleUpload(file: File | undefined) {
    if (!file) return;
    try {
      const created = await upload.mutateAsync({ file });
      setActiveId(created.id);
      notify(`${created.name}을(를) 업로드했습니다.`);
    } catch (error) {
      notify(errorMessage(error, "업로드에 실패했습니다."), "error");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const filtered = datasets.filter((dataset) =>
    dataset.name.toLowerCase().includes(query.toLowerCase()),
  );
  const title = PAGE_TITLES[location.pathname] ?? active?.name ?? "새 데이터로 분석을 시작하세요";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <BarChart3 size={21} />
          </div>
          <div>
            <b>Data BI</b>
            <span>WITH LoL LAB</span>
          </div>
        </div>
        <nav aria-label="주 메뉴">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => (isActive ? "nav-active" : "")}
            >
              <Icon size={17} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-heading">
          <span>데이터셋</span>
          <b>{datasets.length}</b>
        </div>
        <div className="search">
          <Search size={15} />
          <input
            aria-label="데이터셋 검색"
            placeholder="검색"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="dataset-list">
          {filtered.map((dataset) => (
            <button
              key={dataset.id}
              className={active?.id === dataset.id ? "selected" : ""}
              onClick={() => setActiveId(dataset.id)}
            >
              <span className="dataset-icon">
                <Table2 size={15} />
              </span>
              <span>
                <b>{dataset.name}</b>
                <small>
                  {formatInteger(dataset.row_count)}행 · {dataset.column_count ?? 0}열
                </small>
              </span>
            </button>
          ))}
        </div>
        <button className="upload" onClick={() => fileRef.current?.click()}>
          <FileUp size={16} /> 파일 가져오기
        </button>
        <input
          ref={fileRef}
          hidden
          type="file"
          accept=".csv,.xlsx,.xls,.parquet"
          onChange={(event) => void handleUpload(event.target.files?.[0])}
        />
        <div className="sidebar-foot">
          <span className="online-dot" /> Local core <small>DuckDB · Parquet</small>
        </div>
      </aside>

      <main>
        <header>
          <div>
            <p>분석 작업공간</p>
            <h1>{title}</h1>
          </div>
          <div className="header-actions">
            <span className="status">
              <i /> 로컬 전용
            </span>
            <button className="primary" onClick={() => fileRef.current?.click()}>
              <FileUp size={16} /> 업로드
            </button>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
