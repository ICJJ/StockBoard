"use client";

import Sparkline from "./Sparkline";

function fmt(n, d = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

export default function StockCard({ quote, history = [], onRemove }) {
  if (quote.error || quote.current === null || quote.current === 0) {
    return (
      <div className="card">
        <div className="card-top">
          <div>
            <div className="card-sym">{quote.symbol}</div>
            <div className="card-name">{quote.name || ""}</div>
          </div>
          <button className="remove-btn" onClick={() => onRemove(quote.symbol)} title="移除">
            ×
          </button>
        </div>
        <div className="card-error">
          {quote.error ? "无法获取行情" : "暂无数据（非交易时段或代码无效）"}
        </div>
      </div>
    );
  }

  const up = (quote.change ?? 0) >= 0;
  const range = (quote.high ?? 0) - (quote.low ?? 0);
  const markerPct =
    range > 0
      ? Math.min(100, Math.max(0, ((quote.current - quote.low) / range) * 100))
      : 50;

  return (
    <div className="card">
      <div className="card-top">
        <div>
          <div className="card-sym">{quote.symbol}</div>
          <div className="card-name">{quote.name || ""}</div>
        </div>
        <button className="remove-btn" onClick={() => onRemove(quote.symbol)} title="移除">
          ×
        </button>
      </div>

      <div className="card-price">${fmt(quote.current)}</div>
      <div className={`card-change ${up ? "up" : "down"}`}>
        <span>{up ? "▲" : "▼"}</span>
        <span>
          {up ? "+" : ""}
          {fmt(quote.change)} ({up ? "+" : ""}
          {fmt(quote.percent)}%)
        </span>
      </div>

      <Sparkline data={history} up={up} />

      <div className="range">
        <div className="range-track">
          <div className="range-fill" style={{ left: "0%", right: "0%" }} />
          <div className="range-marker" style={{ left: `${markerPct}%` }} />
        </div>
        <div className="range-labels">
          <span>L ${fmt(quote.low)}</span>
          <span>H ${fmt(quote.high)}</span>
        </div>
      </div>

      <div className="card-stats">
        <div>
          <span>Open</span>
          <b>${fmt(quote.open)}</b>
        </div>
        <div>
          <span>Prev</span>
          <b>${fmt(quote.prevClose)}</b>
        </div>
      </div>
    </div>
  );
}
