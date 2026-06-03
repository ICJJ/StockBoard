"use client";

import { useEffect, useState } from "react";
import Nav from "../../components/Nav";
import { tradingApi } from "../../lib/tradingApi";
import EquityChart from "../../components/EquityChart";

const PERIODS = ["1M", "3M", "6M", "1Y", "2Y", "5Y"];
const BARS = [
  { id: "1d", label: "日线" },
  { id: "1h", label: "1小时" },
  { id: "30m", label: "30分" },
  { id: "15m", label: "15分" },
];

function pct(x) {
  return (x >= 0 ? "+" : "") + (x * 100).toFixed(1) + "%";
}

export default function BacktestPage() {
  const [strategies, setStrategies] = useState([]);
  const [strategyId, setStrategyId] = useState("sma_cross");
  const [params, setParams] = useState({});
  const [symbol, setSymbol] = useState("AAPL");
  const [period, setPeriod] = useState("1Y");
  const [bar, setBar] = useState("1d");
  const [cash, setCash] = useState(100000);
  const [commission, setCommission] = useState(1);

  const [backendUp, setBackendUp] = useState(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Load strategy catalog + ping backend.
  useEffect(() => {
    tradingApi
      .strategies()
      .then((j) => {
        setStrategies(j.strategies);
        setBackendUp(true);
      })
      .catch(() => setBackendUp(false));
  }, []);

  // Reset params to defaults when strategy changes.
  const current = strategies.find((s) => s.id === strategyId);
  useEffect(() => {
    if (!current) return;
    const d = {};
    current.params.forEach((p) => (d[p.name] = p.default));
    setParams(d);
  }, [strategyId, strategies]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await tradingApi.backtest({
        symbol,
        strategy: strategyId,
        params,
        period,
        bar,
        initial_cash: Number(cash),
        commission_bps: Number(commission),
      });
      setResult(r);
    } catch (e) {
      setError(e.message);
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  const m = result?.metrics;

  return (
    <div className="container">
      <header className="header">
        <div className="brand">
          <div className="brand-logo">S</div>
          <div>
            <h1>回测 · Backtest</h1>
            <p>基于 IBKR 模拟盘历史数据 · DUP*（paper）</p>
          </div>
        </div>
        <div className="header-meta">
          <span className="market-status">
            <span className={`dot ${backendUp ? "open" : "closed"}`} />
            {backendUp === null ? "连接后端…" : backendUp ? "后端在线" : "后端离线"}
          </span>
          <Nav />
        </div>
      </header>

      {backendUp === false && (
        <div className="notice error">
          连不上交易后端（{tradingApi.base}）。请在 Mac 上启动：
          <br />
          <code>PYTHONPATH=. ./.venv-trading/bin/uvicorn trading.app:app --port 8000</code>
          <br />并确认 TWS 模拟盘已登录、API 已开启。
        </div>
      )}

      <div className="bt-grid">
        {/* Controls */}
        <div className="bt-panel">
          <label className="bt-field">
            <span>股票代码</span>
            <input className="search-input" value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
          </label>

          <label className="bt-field">
            <span>策略</span>
            <select className="search-input" value={strategyId}
              onChange={(e) => setStrategyId(e.target.value)}>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
          </label>

          {current?.params.map((p) => (
            <label className="bt-field" key={p.name}>
              <span>{p.name}（{p.min}–{p.max}）</span>
              <input className="search-input" type="number"
                value={params[p.name] ?? p.default}
                min={p.min} max={p.max}
                onChange={(e) =>
                  setParams((prev) => ({ ...prev, [p.name]: Number(e.target.value) }))
                } />
            </label>
          ))}

          <label className="bt-field">
            <span>区间</span>
            <select className="search-input" value={period}
              onChange={(e) => setPeriod(e.target.value)}>
              {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>

          <label className="bt-field">
            <span>周期</span>
            <select className="search-input" value={bar}
              onChange={(e) => setBar(e.target.value)}>
              {BARS.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
            </select>
          </label>

          <div className="bt-row2">
            <label className="bt-field">
              <span>初始资金</span>
              <input className="search-input" type="number" value={cash}
                onChange={(e) => setCash(e.target.value)} />
            </label>
            <label className="bt-field">
              <span>手续费(bps)</span>
              <input className="search-input" type="number" value={commission}
                onChange={(e) => setCommission(e.target.value)} />
            </label>
          </div>

          <button className="bt-run" onClick={run} disabled={running || !backendUp}>
            {running ? "回测中…" : "▶ 运行回测"}
          </button>
        </div>

        {/* Results */}
        <div className="bt-results">
          {error && <div className="notice error">回测失败：{error}</div>}

          {m && (
            <>
              <div className="bt-metrics">
                <div className={`bt-metric ${m.total_return >= 0 ? "up" : "down"}`}>
                  <span>策略收益</span><b>{pct(m.total_return)}</b>
                </div>
                <div className="bt-metric">
                  <span>买入持有</span><b>{pct(m.buy_hold_return)}</b>
                </div>
                <div className="bt-metric"><span>年化</span><b>{pct(m.cagr)}</b></div>
                <div className="bt-metric"><span>Sharpe</span><b>{m.sharpe}</b></div>
                <div className="bt-metric down"><span>最大回撤</span><b>{pct(m.max_drawdown)}</b></div>
                <div className="bt-metric"><span>交易次数</span><b>{m.num_trades}</b></div>
              </div>
              <EquityChart strategy={result.equity_curve} benchmark={result.buy_hold_curve} />
              <p className="bt-foot">
                {result.symbol} · {result.period} · {m.bars} 根 · 终值 ${m.final_equity.toLocaleString()}
                <br />⚠️ 历史回测不代表未来表现，仅供研究，非投资建议。
              </p>
            </>
          )}

          {!m && !error && (
            <div className="bt-chart-empty">设置参数后点「运行回测」</div>
          )}
        </div>
      </div>
    </div>
  );
}
