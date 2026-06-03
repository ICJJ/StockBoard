"use client";
import { useEffect, useState } from "react";
import { quizApi } from "../../lib/quizApi";

export default function Admin() {
  const [users, setUsers] = useState([]); const [err, setErr] = useState(null);
  const [nu, setNu] = useState(""); const [np, setNp] = useState("");
  async function load() {
    try { setUsers((await quizApi.listUsers()).users); }
    catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, []);
  async function add(e) {
    e.preventDefault();
    try { await quizApi.addUser({ username: nu, password: np }); setNu(""); setNp(""); load(); }
    catch (e) { setErr(e.message); }
  }
  async function toggle(u, disabled) { await quizApi.patchUser(u, { disabled }); load(); }
  return (
    <div className="container" style={{ maxWidth: 560 }}>
      <h1 style={{ margin: "30px 0 16px" }}>账号管理（管理员）</h1>
      {err && <div className="notice error">{err}</div>}
      <form onSubmit={add} className="order-form">
        <input className="search-input" placeholder="新账号" value={nu} onChange={(e) => setNu(e.target.value)} />
        <input className="search-input" placeholder="密码" type="password" value={np} onChange={(e) => setNp(e.target.value)} />
        <button className="bt-run" style={{ maxWidth: 120 }}>添加</button>
      </form>
      <table className="ptable" style={{ marginTop: 16 }}>
        <thead><tr><th>账号</th><th>管理员</th><th>状态</th><th></th></tr></thead>
        <tbody>{users.map((u) => (
          <tr key={u.username}>
            <td className="psym">{u.username}</td>
            <td>{u.is_admin ? "✓" : ""}</td>
            <td>{u.disabled ? "已停用" : "正常"}</td>
            <td><button className="refresh-btn" onClick={() => toggle(u.username, !u.disabled)}>
              {u.disabled ? "启用" : "停用"}</button></td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}
