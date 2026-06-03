"use client";
import { useEffect, useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Quiz() {
  const [q, setQ] = useState(null);
  const [picked, setPicked] = useState(null);
  const [result, setResult] = useState(null);
  const [msg, setMsg] = useState("加载中…");
  const [lang, setLang] = useState("zh");

  useEffect(() => {
    quizApi.state()
      .then((s) => { if (s.entered_today) { window.location.href = "/"; return null; } return quizApi.today(); })
      .then((t) => {
        if (!t) return;
        if (!t.available) { window.location.href = "/"; return; }
        setQ(t); setMsg(null);
      })
      .catch(() => { window.location.href = "/"; });
  }, []);

  async function submit() {
    if (picked == null) return;
    const r = await quizApi.answer(q.id, picked);
    setResult(r);
    if (r.correct) setTimeout(() => (window.location.href = "/"), 800);
  }

  async function feedback(vote) {
    try {
      await quizApi.feedback(q.id, vote);
      setMsg(vote === "remove" ? "已反馈:太专业(将参与剔除)" : "已反馈:保留");
    } catch {}
  }

  if (msg && !q) return <div className="container"><p style={{ padding: 40 }}>{msg}</p></div>;
  if (!q) return null;

  const showZh = q.is_english && lang === "zh";
  const dPrompt = showZh && q.prompt_zh ? q.prompt_zh : q.prompt;
  const dOpts = showZh && q.options_zh ? q.options_zh : q.options;

  return (
    <div className="container" style={{ maxWidth: 640 }}>
      <h1 style={{ margin: "30px 0 6px" }}>每日一题</h1>
      <p style={{ color: "var(--text-dim)", marginBottom: 18 }}>答对才能进入看板;答错会显示答案,可重试。</p>
      <div className="bt-panel">
        <div style={{ fontSize: 16, marginBottom: 16 }}>{dPrompt}</div>
        {q.is_english && (
          <button className="refresh-btn" style={{ marginBottom: 10 }}
            onClick={() => setLang(lang === "zh" ? "en" : "zh")}>
            {lang === "zh" ? "🌐 看英文原文" : "🌐 看中文"}
          </button>
        )}
        {dOpts.map((opt, i) => {
          const isAnswer = result && !result.correct && result.correct_index === i;
          const isPicked = picked === i;
          return (
            <button key={i}
              onClick={() => !result?.correct && setPicked(i)}
              className="quiz-opt"
              style={{
                borderColor: isAnswer ? "var(--green)" : isPicked ? "var(--accent)" : "var(--border)",
                color: isAnswer ? "var(--green)" : "var(--text)",
              }}>
              {String.fromCharCode(65 + i)}. {opt}
            </button>
          );
        })}
        {!result?.correct && (
          <button className="bt-run" style={{ marginTop: 12 }} onClick={submit} disabled={picked == null}>
            提交
          </button>
        )}
        {result && !result.correct && (
          <div className="notice error" style={{ marginTop: 12 }}>
            答错了。正确答案:{String.fromCharCode(65 + result.correct_index)}。{lang === "zh" && result.explanation_zh ? result.explanation_zh : result.explanation}
            <div style={{ marginTop: 8 }}>再选一次并提交即可进入。</div>
          </div>
        )}
        {result?.correct && (
          <div className="order-msg ok" style={{ marginTop: 12 }}>
            {result.scored ? "答对!首答得分 ✅ 正在进入…" : "答对!正在进入…"}
          </div>
        )}
        <div className="refresh-row" style={{ marginTop: 14 }}>
          <span style={{ color: "var(--text-faint)", fontSize: 12 }}>这题:</span>
          <button className="refresh-btn" onClick={() => feedback("keep")}>保留</button>
          <button className="refresh-btn" onClick={() => feedback("remove")}>太专业，剔除</button>
          {msg && q && <span style={{ color: "var(--text-dim)", fontSize: 12 }}>{msg}</span>}
        </div>
      </div>
      <p className="footer"><a href="/leaderboard">查看排行榜 →</a></p>
    </div>
  );
}
