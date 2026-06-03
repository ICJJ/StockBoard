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

  // Order form
  const [ord, setOrd] = useState({ symbol: "AAPL", side: "BUY", quantity: 10, order_type: "MARKET", limit_price: "" });
  const [preview, setPreview] = useState(null);
  const [orderMsg, setOrderMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  function orderBody(dry) {
    return {
      symbol: ord.symbol.toUpperCase(),
      side: ord.side,
      quantity: Number(ord.quantity),
      order_type: ord.order_type,
      limit_price: ord.order_type === "LIMIT" ? Number(ord.limit_price) : null,
      dry_run: dry,
    };
  }

  async function doPreview() {
    setBusy(true); setOrderMsg(null);
    try {
      setPreview(await tradingApi.paperOrder(orderBody(true)));
    } catch (e) {
      setOrderMsg({ ok: false, text: e.message }); setPreview(null);
    } finally { setBusy(false); }
  }

  async function doSubmit() {
    setBusy(true);
    try {
      const r = await tradingApi.paperOrder(orderBody(false));
      setOrderMsg({ ok: true, text: `已提交模拟单 #${r.order_id}（${r.status}）` });
      setPreview(null);
      load();
    } catch (e) {
      setOrderMsg({ ok: false, text: e.message });
    } finally { setBusy(false); }
  }

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

      <div className="order-card">
        <h2>模拟下单 <span className="order-tag">仅 DU* 模拟盘 · 真实账户被硬性拒绝</span></h2>
        <div className="order-form">
          <label className="bt-field">
            <span>代码</span>
            <input className="search-input" value={ord.symbol}
              onChange={(e) => setOrd({ ...ord, symbol: e.target.value.toUpperCase() })} />
          </label>
          <label className="bt-field">
            <span>方向</span>
            <select className="search-input" value={ord.side}
              onChange={(e) => setOrd({ ...ord, side: e.target.value })}>
              <option value="BUY">买入 BUY</option>
              <option value="SELL">卖出 SELL</option>
            </select>
          </label>
          <label className="bt-field">
            <span>数量(股)</span>
            <input className="search-input" type="number" value={ord.quantity}
              onChange={(e) => setOrd({ ...ord, quantity: e.target.value })} />
          </label>
          <label className="bt-field">
            <span>类型</span>
            <select className="search-input" value={ord.order_type}
              onChange={(e) => setOrd({ ...ord, order_type: e.target.value })}>
              <option value="MARKET">市价 MARKET</option>
              <option value="LIMIT">限价 LIMIT</option>
            </select>
          </label>
          {ord.order_type === "LIMIT" && (
            <label className="bt-field">
              <span>限价</span>
              <input className="search-input" type="number" value={ord.limit_price}
                onChange={(e) => setOrd({ ...ord, limit_price: e.target.value })} />
            </label>
          )}
        </div>

        {!preview ? (
          <button className="bt-run" style={{ maxWidth: 220 }} onClick={doPreview} disabled={busy}>
            {busy ? "…" : "预览(dry-run)"}
          </button>
        ) : (
          <div className="order-confirm">
            <div className="order-preview">
              即将在 <b>{preview.account}</b> 下单:
              <b className={preview.side === "BUY" ? "up" : "down"}> {preview.side} {preview.quantity} {preview.symbol}</b>
              {" "}({preview.order_type}{preview.limit_price ? ` @ ${preview.limit_price}` : ""}, {preview.tif})
            </div>
            <div className="refresh-row">
              <button className="bt-run" style={{ maxWidth: 200 }} onClick={doSubmit} disabled={busy}>
                {busy ? "提交中…" : "✓ 确认下模拟单"}
              </button>
              <button className="refresh-btn" onClick={() => setPreview(null)}>取消</button>
            </div>
          </div>
        )}

        {orderMsg && (
          <div className={`order-msg ${orderMsg.ok ? "ok" : "err"}`}>{orderMsg.text}</div>
        )}
      </div>
    </div>
  );
}
