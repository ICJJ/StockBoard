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

  const [mode, setMode] = useState("single"); // single | sweep
  const [grid, setGrid] = useState({}); // param -> csv string of values
  const [sortBy, setSortBy] = useState("sharpe");
  const [sweep, setSweep] = useState(null);
  const [valid, setValid] = useState(null);
  const [validating, setValidating] = useState(false);

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
    const g = {};
    current.params.forEach((p) => {
      d[p.name] = p.default;
      // sensible default sweep range around the default
      g[p.name] = [p.default, Math.round(p.default * 1.5), p.default * 2]
        .filter((v) => v >= p.min && v <= p.max)
        .join(", ");
    });
    setParams(d);
    setGrid(g);
  }, [strategyId, strategies]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run() {
    setRunning(true);
    setError(null);
    setValid(null);
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

  async function runSweep() {
    setRunning(true);
    setError(null);
    try {
      const parsedGrid = {};
      (current?.params || []).forEach((p) => {
        parsedGrid[p.name] = String(grid[p.name] || "")
          .split(",")
          .map((s) => Number(s.trim()))
          .filter((n) => !Number.isNaN(n));
      });
      const r = await tradingApi.sweep({
        symbol,
        strategy: strategyId,
        grid: parsedGrid,
        period,
        bar,
        initial_cash: Number(cash),
        commission_bps: Number(commission),
        sort_by: sortBy,
      });
      setSweep(r);
    } catch (e) {
      setError(e.message);
      setSweep(null);
    } finally {
      setRunning(false);
    }
  }

  // Load one sweep row's params into single mode and run it.
  function loadCombo(p) {
    setParams(p);
    setMode("single");
    setTimeout(run, 0);
  }

  async function runValidate() {
    setValidating(true);
    setValid(null);
    try {
      setValid(await tradingApi.validate({
        symbol, strategy: strategyId, params,
        period: period === "1M" || period === "3M" ? "1Y" : period,
        bar, commission_bps: Number(commission),
      }));
    } catch (e) {
      setValid({ error: e.message });
    } finally {
      setValidating(false);
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

          <div className="bt-modes">
            <button className={mode === "single" ? "active" : ""} onClick={() => setMode("single")}>单次回测</button>
            <button className={mode === "sweep" ? "active" : ""} onClick={() => setMode("sweep")}>参数扫描</button>
          </div>

          {mode === "single"
            ? current?.params.map((p) => (
                <label className="bt-field" key={p.name}>
                  <span>{p.name}（{p.min}–{p.max}）</span>
                  <input className="search-input" type="number"
                    value={params[p.name] ?? p.default}
                    min={p.min} max={p.max}
                    onChange={(e) =>
                      setParams((prev) => ({ ...prev, [p.name]: Number(e.target.value) }))
                    } />
                </label>
              ))
            : (
              <>
                {current?.params.map((p) => (
                  <label className="bt-field" key={p.name}>
                    <span>{p.name} 值列表（逗号分隔）</span>
                    <input className="search-input" value={grid[p.name] ?? ""}
                      placeholder="例如 10, 20, 30"
                      onChange={(e) => setGrid((prev) => ({ ...prev, [p.name]: e.target.value }))} />
                  </label>
                ))}
                <label className="bt-field">
                  <span>排序指标</span>
                  <select className="search-input" value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}>
                    <option value="sharpe">Sharpe（高→低）</option>
                    <option value="total_return">总收益（高→低）</option>
                    <option value="cagr">年化（高→低）</option>
                    <option value="max_drawdown">回撤（小→大）</option>
                  </select>
                </label>
              </>
            )}

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

          <button className="bt-run" onClick={mode === "single" ? run : runSweep}
            disabled={running || !backendUp}>
            {running
              ? (mode === "single" ? "回测中…" : "扫描中…")
              : (mode === "single" ? "▶ 运行回测" : "▶ 运行扫描")}
          </button>
        </div>

        {/* Results */}
        <div className="bt-results">
          {error && <div className="notice error">回测失败：{error}</div>}

          {mode === "single" && m && (
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

              <button className="refresh-btn" onClick={runValidate} disabled={validating}
                style={{ marginTop: 4 }}>
                {validating ? "校验中…" : "🔬 校验稳健性（样本外 + 随机对照）"}
              </button>
              {valid && !valid.error && (
                <div className="bt-validate">
                  <div className="bt-vrow">
                    <span>样本内 Sharpe</span><b>{valid.in_sample.sharpe}</b>
                    <span>样本外 Sharpe</span>
                    <b className={valid.verdict.overfit ? "down" : "up"}>{valid.out_of_sample.sharpe}</b>
                  </div>
                  <div className="bt-vrow">
                    <span>策略收益</span><b>{pct(valid.random_control.strategy_return)}</b>
                    <span>随机同敞口(中位)</span><b>{pct(valid.random_control.median_return)}</b>
                  </div>
                  <div className="bt-vrow">
                    <span>跑赢随机比例</span>
                    <b className={valid.verdict.beats_random ? "up" : "down"}>
                      {(valid.random_control.percentile * 100).toFixed(0)}%
                    </b>
                    <span>择时超额</span>
                    <b className={valid.random_control.edge_vs_random >= 0 ? "up" : "down"}>
                      {pct(valid.random_control.edge_vs_random)}
                    </b>
                  </div>
                  {valid.verdict.notes.map((nt, i) => (
                    <p key={i} className={`bt-vnote ${valid.verdict.overfit || !valid.verdict.beats_random ? "warn" : "ok"}`}>
                      {valid.verdict.overfit || !valid.verdict.beats_random ? "⚠️ " : "✓ "}{nt}
                    </p>
                  ))}
                </div>
              )}
              {valid?.error && <div className="card-error">校验失败：{valid.error}</div>}
            </>
          )}

          {mode === "sweep" && sweep && (
            <>
              <p className="bt-foot" style={{ marginTop: 0, marginBottom: 10 }}>
                {sweep.symbol} · {sweep.count} 组结果 · 按 {sweep.sort_by} 排序
                {sweep.truncated ? "（已截断至前 200 组）" : ""} · 点行加载到单次回测
              </p>
              <table className="ptable">
                <thead>
                  <tr><th>参数</th><th>总收益</th><th>买入持有</th><th>Sharpe</th><th>最大回撤</th><th>交易</th></tr>
                </thead>
                <tbody>
                  {sweep.results.map((r, i) => (
                    <tr key={i} onClick={() => loadCombo(r.params)} style={{ cursor: "pointer" }}>
                      <td className="psym">{Object.entries(r.params).map(([k, v]) => `${k}=${v}`).join(" ")}</td>
                      <td className={r.metrics.total_return >= 0 ? "up" : "down"}>{pct(r.metrics.total_return)}</td>
                      <td>{pct(r.metrics.buy_hold_return)}</td>
                      <td>{r.metrics.sharpe}</td>
                      <td className="down">{pct(r.metrics.max_drawdown)}</td>
                      <td>{r.metrics.num_trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {((mode === "single" && !m) || (mode === "sweep" && !sweep)) && !error && (
            <div className="bt-chart-empty">
              {mode === "single" ? "设置参数后点「运行回测」" : "填写参数值列表后点「运行扫描」"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
