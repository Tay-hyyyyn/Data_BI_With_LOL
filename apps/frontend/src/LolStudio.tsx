import { useMemo, useState } from "react";
import { BarChart3, DatabaseZap, Download, FileUp, Gamepad2, Play, ShieldCheck } from "lucide-react";
import { api } from "./api";
import type { Dataset, RiotAccount, RiotMatchCollection } from "./types";

export function LolStudio({ datasets, onDatasetsChanged }: { datasets: Dataset[]; onDatasetsChanged: () => Promise<void> }) {
  const [version, setVersion] = useState("");
  const [gameName, setGameName] = useState("");
  const [tagLine, setTagLine] = useState("KR1");
  const [count, setCount] = useState(5);
  const [account, setAccount] = useState<RiotAccount | null>(null);
  const [collection, setCollection] = useState<RiotMatchCollection | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [benchmarkFile, setBenchmarkFile] = useState<File | null>(null);
  const [starterPatch, setStarterPatch] = useState("");
  const itemDatasets = useMemo(() => datasets.filter((item) => item.source_type === "riot-data-dragon" && item.name.startsWith("LoL items ")), [datasets]);

  async function syncStatic() {
    setBusy("static"); setMessage("");
    try { const result = await api.syncLolStatic(version); await onDatasetsChanged(); setMessage(`${result.patch} 아이템·챔피언·룬·스탯 가치 데이터셋을 생성했습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "정적 데이터 동기화에 실패했습니다."); }
    finally { setBusy(""); }
  }
  async function resolve() {
    setBusy("account"); setMessage(""); setCollection(null);
    try { const result = await api.resolveRiotAccount(gameName, tagLine); setAccount(result); setMessage(`${result.game_name}#${result.tag_line} 계정을 확인했습니다.`); }
    catch (error) { setAccount(null); setMessage(error instanceof Error ? error.message : "계정을 찾지 못했습니다."); }
    finally { setBusy(""); }
  }
  async function collect() {
    if (!account) return;
    setBusy("collect"); setMessage("");
    try { const result = await api.collectLolMatches(account.puuid, count); setCollection(result); setMessage(`신규 ${result.fetched}경기, 기존 ${result.cached}경기를 준비했습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "경기 수집에 실패했습니다."); }
    finally { setBusy(""); }
  }
  async function process() {
    if (!collection?.matches.length) return;
    setBusy("process"); setMessage("");
    try { const result = await api.processLolMatchesGrouped(collection.matches.map((item) => item.match_id)); await onDatasetsChanged(); setMessage(`${Object.keys(result.patches).length}개 패치를 분리 처리하고 통합 추세·표본 품질 마트를 게시했습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "경기 처리에 실패했습니다."); }
    finally { setBusy(""); }
  }
  async function uploadBenchmark() {
    if (!benchmarkFile) return;
    setBusy("benchmark"); setMessage("");
    try { const result = await api.uploadLolpsBenchmark(benchmarkFile); await onDatasetsChanged(); setMessage(`${result.name} 벤치마크를 비공개 데이터셋으로 등록했습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "벤치마크 등록에 실패했습니다."); }
    finally { setBusy(""); }
  }
  async function createStarterDashboard() {
    if (!starterPatch) return;
    setBusy("dashboard"); setMessage("");
    try { const result = await api.createLolStarterDashboard(starterPatch); setMessage(`${result.name}를 비공개로 저장했습니다. 대시보드 탭에서 불러올 수 있습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "대시보드 생성에 실패했습니다."); }
    finally { setBusy(""); }
  }
  async function createPatchTrendDashboard() {
    setBusy("patch-dashboard"); setMessage("");
    try { const result = await api.createLolPatchTrendDashboard(); setMessage(`${result.name}를 비공개로 저장했습니다. 대시보드 탭에서 불러올 수 있습니다.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "비교 대시보드를 생성하지 못했습니다."); }
    finally { setBusy(""); }
  }

  return <section className="studio lol-studio">
    <div className="lol-safety"><ShieldCheck size={18}/><div><b>개발 데이터 보호 적용</b><span>원본 경기와 파생 데이터는 로컬 비공개로 유지되며 공개 게시가 차단됩니다.</span></div></div>
    {message && <div className="notice">{message}</div>}
    <div className="lol-grid">
      <article className="panel lol-card"><div className="panel-head"><div><p>STEP 1</p><h2>패치 정적 데이터</h2></div><DatabaseZap size={19}/></div><label>Data Dragon 버전<input placeholder="비우면 최신 버전" value={version} onChange={(event) => setVersion(event.target.value)}/></label><button className="primary" disabled={!!busy} onClick={() => void syncStatic()}><Download size={16}/>{busy === "static" ? "동기화 중" : "아이템·챔피언·룬 동기화"}</button></article>
      <article className="panel lol-card"><div className="panel-head"><div><p>STEP 2</p><h2>Riot ID 확인</h2></div><Gamepad2 size={19}/></div><div className="riot-id-row"><label>게임 이름<input value={gameName} onChange={(event) => setGameName(event.target.value)}/></label><label>태그<input value={tagLine} onChange={(event) => setTagLine(event.target.value.replace(/^#/, ""))}/></label></div><button className="primary" disabled={!!busy || !gameName || !tagLine} onClick={() => void resolve()}>{busy === "account" ? "확인 중" : "계정 확인"}</button></article>
      <article className="panel lol-card"><div className="panel-head"><div><p>STEP 3</p><h2>최근 경기 수집</h2></div><Download size={19}/></div><label>경기 수<input type="number" min={1} max={20} value={count} onChange={(event) => setCount(Math.min(20, Math.max(1, Number(event.target.value))))}/></label><button className="primary" disabled={!!busy || !account} onClick={() => void collect()}>{busy === "collect" ? "호출 한도에 맞춰 수집 중" : "Match·Timeline 수집"}</button><small>Development Key 장기 한도에 맞춰 요청 간격을 자동 조절합니다.</small></article>
      <article className="panel lol-card"><div className="panel-head"><div><p>STEP 4</p><h2>분석 마트 생성</h2></div><Play size={19}/></div><p className="lol-card-copy">수집한 경기를 패치별로 분리하고, 해당 Data Dragon 아이템 버전과 자동 매핑합니다.</p><button className="primary" disabled={!!busy || !collection?.matches.length} onClick={() => void process()}>{busy === "process" ? "정규화 중" : "10·15·20분 마트 생성"}</button><small>여러 패치가 섞여도 골드·스탯 추세 비교용 통합 마트를 함께 만듭니다.</small></article>
      <article className="panel lol-card"><div className="panel-head"><div><p>OPTIONAL</p><h2>LOL.PS 벤치마크</h2></div><FileUp size={19}/></div><label>허가받은 집계 파일<input type="file" accept=".csv,.xlsx,.xls,.parquet" onChange={(event) => setBenchmarkFile(event.target.files?.[0] ?? null)}/></label><button className="primary" disabled={!!busy || !benchmarkFile} onClick={() => void uploadBenchmark()}>{busy === "benchmark" ? "검증 중" : "집계 벤치마크 등록"}</button><small>비공개 API 호출 없이 제공받은 파일만 등록하며, 승률·픽률은 0~1로 표준화합니다.</small></article>
      <article className="panel lol-card"><div className="panel-head"><div><p>STEP 5</p><h2>BI 시작 대시보드</h2></div><BarChart3 size={19}/></div><label>분석 패치<select value={starterPatch} onChange={(event) => setStarterPatch(event.target.value)}><option value="">패치를 선택하세요</option>{itemDatasets.map((item) => <option key={item.id} value={item.name.replace("LoL items ", "")}>{item.name.replace("LoL items ", "")}</option>)}</select></label><button className="primary" disabled={!!busy || !starterPatch} onClick={() => void createStarterDashboard()}>{busy === "dashboard" ? "생성 중" : "골드·승률 대시보드 만들기"}</button><small>선택한 패치의 골드, AP·AD·AH, 관찰 승률 위젯을 비공개로 저장합니다.</small></article>
      <article className="panel lol-card"><div className="panel-head"><div><p>STEP 6</p><h2>패치 비교 대시보드</h2></div><BarChart3 size={19}/></div><p className="lol-card-copy">분리 처리한 여러 패치의 골드·인벤토리 스탯과 표본 품질을 같은 시간축에서 비교합니다.</p><button className="primary" disabled={!!busy} onClick={() => void createPatchTrendDashboard()}>{busy === "patch-dashboard" ? "생성 중" : "패치 추세 비교 만들기"}</button><small>통합 추세와 표본 품질 마트가 있어야 하며, 비공개로 저장됩니다.</small></article>
    </div>
    {collection && <article className="panel match-summary"><b>수집 준비 완료</b><span>{collection.matches.length}경기 · 신규 {collection.fetched} · 캐시 {collection.cached}</span><div>{collection.matches.map((item) => <code key={item.match_id}>{item.match_id}{item.cached ? " · cached" : " · new"}</code>)}</div></article>}
  </section>;
}
