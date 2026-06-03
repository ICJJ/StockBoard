"use client";

import { useEffect, useState } from "react";
import Nav from "../../components/Nav";
import { tradingApi } from "../../lib/tradingApi";

function usd(n) {
  if (n === null || n === undefined) return "—";
  return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function LivePage() {
  const [snap, setSnap] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setSnap(await tradingApi.live());
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => { load(); }, []);

  const positions = snap?.positions || [];

  return (
    <div className="container">
      <header className="header">
        <div className="brand">
          <div className="brand-logo">S</div>
          <div>
            <h1>实盘 · Live（只读）</h1>
            <p>经官方 IBKR connector 拉取的只读快照</p>
          </div>
        </div>
        <div className="header-meta">
          <Nav />
        </div>
      </header>

      <div className="notice" style={{ borderColor: "var(--accent)", color: "var(--text-dim)", textAlign: "left" }}>
        🔒 <b>只读</b>：此页仅展示实盘快照,<b>不提供任何下单/交易功能</b>。数据来源:{snap?.source || "官方 IBKR connector"}。
        {snap?.updated_at && <><br />快照时间(UTC):{snap.updated_at} · 由 Claude 通过官方连接器更新,非实时。</>}
      </div>

      {error && <div className="notice error">读取实盘快照失败:{error}</div>}

      {snap?.available && (
        <>
          <div className="bt-metrics" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            <div className="bt-metric"><span>净值</span><b>{usd(snap.net_liquidation)}</b></div>
            <div className="bt-metric"><span>现金</span><b>{usd(snap.total_cash)}</b></div>
            <div className="bt-metric"><span>持仓市值</span><b>{usd(snap.total_market_value)}</b></div>
            <div className={`bt-metric ${snap.total_unrealized_pnl >= 0 ? "up" : "down"}`}>
              <span>未实现盈亏</span><b>{usd(snap.total_unrealized_pnl)}</b>
            </div>
          </div>

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
        </>
      )}

      {snap && !snap.available && !error && (
        <div className="empty">尚无实盘快照。让 Claude 通过官方连接器更新一次即可。</div>
      )}
    </div>
  );
}
