import { FormEvent, useState } from "react";
import { LockKeyhole } from "lucide-react";
import { api } from "./api";
import type { AuthStatus } from "./types";

export function LoginScreen({ onLoggedIn }: { onLoggedIn: (status: AuthStatus) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { onLoggedIn(await api.login(email, password)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "로그인에 실패했습니다."); }
    finally { setBusy(false); }
  }
  return <main className="login-shell"><form className="login-card" onSubmit={(event) => void submit(event)}><div className="brand-mark"><LockKeyhole size={22}/></div><p>Data BI WITH LoL LAB</p><h1>분석 작업공간 로그인</h1><label>이메일<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required/></label><label>비밀번호<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required/></label>{error && <div className="error">{error}</div>}<button className="primary" disabled={busy}>{busy ? "확인 중…" : "로그인"}</button></form></main>;
}
