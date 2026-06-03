"use client";
import { useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Login() {
  const [u, setU] = useState(""); const [p, setP] = useState("");
  const [err, setErr] = useState(null); const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await quizApi.login(u, p); window.location.href = "/"; }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="container" style={{ maxWidth: 360 }}>
      <h1 style={{ margin: "40px 0 20px" }}>StockBoard 登录</h1>
      <form onSubmit={submit} className="bt-panel">
        <label className="bt-field"><span>账号</span>
          <input className="search-input" value={u} onChange={(e) => setU(e.target.value)} /></label>
        <label className="bt-field"><span>密码</span>
          <input className="search-input" type="password" value={p} onChange={(e) => setP(e.target.value)} /></label>
        <button className="bt-run" disabled={busy}>{busy ? "…" : "登录"}</button>
        {err && <div className="notice error">{err}</div>}
      </form>
    </div>
  );
}
