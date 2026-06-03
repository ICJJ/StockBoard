"use client";
import { useEffect, useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Leaderboard() {
  const [rows, setRows] = useState([]); const [err, setErr] = useState(null);
  useEffect(() => { quizApi.leaderboard().then((d) => setRows(d.leaderboard)).catch((e) => setErr(e.message)); }, []);
  return (
    <div className="container" style={{ maxWidth: 560 }}>
      <h1 style={{ margin: "30px 0 16px" }}>排行榜</h1>
      {err && <div className="notice error">{err}</div>}
      <table className="ptable">
        <thead><tr><th>#</th><th>账号</th><th>积分</th><th>连续</th><th>正确率</th></tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={r.username}>
            <td>{i + 1}</td><td className="psym">{r.username}</td>
            <td><b>{r.points}</b></td><td>{r.streak}</td>
            <td>{Math.round((r.accuracy || 0) * 100)}%</td>
          </tr>))}</tbody>
      </table>
      <p className="footer"><a href="/">← 返回看板</a></p>
    </div>
  );
}
