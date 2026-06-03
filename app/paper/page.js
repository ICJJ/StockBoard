"use client";

import { useEffect, useState } from "react";
import Nav from "../../components/Nav";
import { tradingApi } from "../../lib/tradingApi";

function usd(n) {
  if (n === null || n === undefined) return "—";
  return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PaperPage() {
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [a, p] = await Promise.all([
        tradingApi.paperAccount(),
        tradingApi.paperPositions(),
      ]);
      setAccount(a);
      setPositions(p.positions);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const totalPnl = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);

  return (
    <div className="container">
      <header className="header">
        <div className="brand">
          <div className="brand-logo">S</div>
          <div>
            <h1>模拟盘 · Paper</h1>
            <p>{account ? `${account.account}（模拟）` : "IBKR 本地模拟盘"}</p>
          </div>
        </div>
        <div className="header-meta">
          <Nav />
          <button className="refresh-btn" onClick={load}>刷新</button>
        </div>
      </header>

      {error && (
        <div className="notice error">
          连不上交易后端（{tradingApi.base}）：{error}
          <br />请在 Mac 上启动后端并确认 TWS 模拟盘已登录。
        </div>
      )}

      {account && (
        <div className="bt-metrics" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
          <div className="bt-metric"><span>净值</span><b>{usd(account.net_liquidation)}</b></div>
          <div className="bt-metric"><span>现金</span><b>{usd(account.total_cash)}</b></div>
          <div className="bt-metric"><span>购买力</span><b>{usd(account.buying_power)}</b></div>
          <div className={`bt-metric ${totalPnl >= 0 ? "up" : "down"}`}>
            <span>未实现盈亏</span><b>{usd(totalPnl)}</b>
          </div>
        </div>
      )}

      {loading && !account ? (
        <div className="empty">加载中…</div>
      ) : positions.length ? (
        <table className="ptable">
          <thead>
            <tr><th>代码</th><th>持仓</th><th>成本</th><th>现价</th><th>市值</th><th>未实现盈亏</th></tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.symbol}>
                <td className="psym">{p.symbol}</td>
                <td>{p.position}</td>
                <td>{usd(p.avg_cost)}</td>
                <td>{usd(p.market_price)}</td>
                <td>{usd(p.market_value)}</td>
                <td className={(p.unrealized_pnl || 0) >= 0 ? "up" : "down"}>{usd(p.unrealized_pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        !error && <div className="empty">模拟盘暂无持仓</div>
      )}
    </div>
  );
}
