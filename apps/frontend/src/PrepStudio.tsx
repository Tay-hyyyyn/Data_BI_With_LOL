import { useState } from "react";
import { Check, Plus, Play, Trash2 } from "lucide-react";
import { api } from "./api";
import type { Dataset, Profile } from "./types";

type Step = { operation: "drop_duplicates" | "fill_missing"; config: Record<string, unknown>; label: string };

export function PrepStudio({ dataset, profile, onPublished }: { dataset: Dataset | null; profile: Profile | null; onPublished: () => Promise<void> }) {
  const [operation, setOperation] = useState<Step["operation"]>("drop_duplicates");
  const [column, setColumn] = useState("");
  const [value, setValue] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const columns = profile?.columns ?? [];
  function add() {
    if (!column) return;
    const step = operation === "drop_duplicates"
      ? { operation, config: { columns: [column] }, label: `${column} 중복 제거` } as Step
      : { operation, config: { column, method: "value", value }, label: `${column} 결측값 → ${value || "빈 값"}` } as Step;
    setSteps((current) => [...current, step]);
  }
  async function run() {
    if (!dataset || steps.length === 0) return;
    setBusy(true); setMessage("");
    try { const result = await api.transform(dataset.id, { name: "웹 전처리 레시피", steps: steps.map(({ operation, config }) => ({ operation, config })) }); await onPublished(); setSteps([]); setMessage(`새 버전 v${String(result.version_number)}을 게시했습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "전처리에 실패했습니다."); }
    finally { setBusy(false); }
  }
  if (!dataset || !profile) return <section className="empty"><h2>먼저 데이터셋을 선택하세요</h2></section>;
  return <section className="studio prep-layout"><article className="panel recipe-builder"><div className="panel-head"><div><p>전처리 레시피</p><h2>순서대로 실행할 작업</h2></div></div><label>작업<select value={operation} onChange={(event) => setOperation(event.target.value as Step["operation"])}><option value="drop_duplicates">중복 제거</option><option value="fill_missing">결측값 채우기</option></select></label><label>대상 컬럼<select value={column} onChange={(event) => setColumn(event.target.value)}><option value="">선택</option>{columns.map((item) => <option key={item.name}>{item.name}</option>)}</select></label>{operation === "fill_missing" && <label>대체 값<input value={value} onChange={(event) => setValue(event.target.value)}/></label>}<button className="primary" onClick={add}><Plus size={16}/> 작업 추가</button></article><article className="panel recipe-steps"><div className="panel-head"><div><p>실행 순서</p><h2>{steps.length}개 작업</h2></div></div>{steps.length === 0 ? <div className="recommend-placeholder">왼쪽에서 작업을 추가하세요.</div> : steps.map((step, index) => <div className="recipe-step" key={`${step.label}-${index}`}><span>{index + 1}</span><Check size={15}/><b>{step.label}</b><button onClick={() => setSteps((current) => current.filter((_, i) => i !== index))}><Trash2 size={15}/></button></div>)}<button className="primary run-recipe" disabled={busy || steps.length === 0} onClick={() => void run()}><Play size={16}/> {busy ? "게시 중" : "새 버전 게시"}</button>{message && <div className="notice">{message}</div>}</article></section>;
}
