import { useEffect, useState } from "react";
import { Check, Plus, Play, Trash2 } from "lucide-react";
import { api } from "./api";
import type { Dataset, Profile } from "./types";

type Operation = "drop_duplicates" | "fill_missing" | "join";
type Step = { operation: Operation; config: Record<string, unknown>; label: string };

export function PrepStudio({ dataset, datasets, profile, onPublished }: { dataset: Dataset | null; datasets: Dataset[]; profile: Profile | null; onPublished: () => Promise<void> }) {
  const [operation, setOperation] = useState<Operation>("drop_duplicates");
  const [column, setColumn] = useState("");
  const [value, setValue] = useState("");
  const [joinDatasetId, setJoinDatasetId] = useState("");
  const [joinProfile, setJoinProfile] = useState<Profile | null>(null);
  const [joinColumn, setJoinColumn] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const columns = profile?.columns ?? [];
  const joinable = datasets.filter((item) => item.id !== dataset?.id && item.current_version_id);

  useEffect(() => {
    if (!joinDatasetId) { setJoinProfile(null); setJoinColumn(""); return; }
    api.profile(joinDatasetId).then((next) => { setJoinProfile(next); setJoinColumn(next.columns[0]?.name ?? ""); }).catch(() => { setJoinProfile(null); setJoinColumn(""); });
  }, [joinDatasetId]);

  function add() {
    if (!column) return;
    if (operation === "join") {
      if (!joinDatasetId || !joinColumn) return;
      setSteps((current) => [...current, { operation, config: { right_dataset_id: joinDatasetId, left_on: [column], right_on: [joinColumn], how: "left" }, label: `${column} = ${joinColumn} · 왼쪽 조인` }]);
      return;
    }
    const step = operation === "drop_duplicates"
      ? { operation, config: { columns: [column] }, label: `${column} 중복 제거` } as Step
      : { operation, config: { column, method: "value", value }, label: `${column} 결측값 → ${value || "빈 값"}` } as Step;
    setSteps((current) => [...current, step]);
  }
  async function run() {
    if (!dataset || steps.length === 0) return;
    setBusy(true); setMessage("");
    try { const result = await api.transform(dataset.id, { name: "웹 전처리 레시피", steps: steps.map(({ operation: stepOperation, config }) => ({ operation: stepOperation, config })) }); await onPublished(); setSteps([]); setMessage(`새 버전 v${String(result.version_number)}을 게시했습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "전처리에 실패했습니다."); }
    finally { setBusy(false); }
  }
  if (!dataset || !profile) return <section className="empty"><h2>먼저 데이터셋을 선택하세요</h2></section>;
  return <section className="studio prep-layout"><article className="panel recipe-builder"><div className="panel-head"><div><p>전처리 레시피</p><h2>순서대로 실행할 작업</h2></div></div><label>작업<select value={operation} onChange={(event) => setOperation(event.target.value as Operation)}><option value="drop_duplicates">중복 제거</option><option value="fill_missing">결측값 채우기</option><option value="join">다른 데이터셋 조인</option></select></label><label>{operation === "join" ? "왼쪽 조인 키" : "대상 컬럼"}<select value={column} onChange={(event) => setColumn(event.target.value)}><option value="">선택</option>{columns.map((item) => <option key={item.name}>{item.name}</option>)}</select></label>{operation === "fill_missing" && <label>대체 값<input value={value} onChange={(event) => setValue(event.target.value)}/></label>}{operation === "join" && <><label>오른쪽 데이터셋<select value={joinDatasetId} onChange={(event) => setJoinDatasetId(event.target.value)}><option value="">선택</option>{joinable.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>오른쪽 조인 키<select value={joinColumn} disabled={!joinProfile} onChange={(event) => setJoinColumn(event.target.value)}><option value="">선택</option>{joinProfile?.columns.map((item) => <option key={item.name}>{item.name}</option>)}</select></label><small>기본은 왼쪽 조인입니다. 필요하면 중복 키를 먼저 정리하세요.</small></>}<button className="primary" onClick={add}><Plus size={16}/> 작업 추가</button></article><article className="panel recipe-steps"><div className="panel-head"><div><p>실행 순서</p><h2>{steps.length}개 작업</h2></div></div>{steps.length === 0 ? <div className="recommend-placeholder">왼쪽에서 작업을 추가하세요.</div> : steps.map((step, index) => <div className="recipe-step" key={`${step.label}-${index}`}><span>{index + 1}</span><Check size={15}/><b>{step.label}</b><button onClick={() => setSteps((current) => current.filter((_, i) => i !== index))}><Trash2 size={15}/></button></div>)}<button className="primary run-recipe" disabled={busy || steps.length === 0} onClick={() => void run()}><Play size={16}/> {busy ? "게시 중" : "새 버전 게시"}</button>{message && <div className="notice">{message}</div>}</article></section>;
}
