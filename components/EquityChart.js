"use client";

// Dual-line equity curve chart (strategy vs buy & hold), dependency-free SVG.
export default function EquityChart({ strategy = [], benchmark = [], width = 760, height = 280 }) {
  if (!strategy.length) {
    return <div className="bt-chart-empty">运行回测后这里显示资金曲线</div>;
  }

  const padL = 56, padR = 16, padT = 14, padB = 28;
  const sVals = strategy.map((p) => p.value);
  const bVals = benchmark.map((p) => p.value);
  const all = sVals.concat(bVals);
  const min = Math.min(...all);
  const max = Math.max(...all);
  const range = max - min || 1;
  const n = strategy.length;

  const x = (i) => padL + (i / (n - 1)) * (width - padL - padR);
  const y = (v) => padT + (1 - (v - min) / range) * (height - padT - padB);

  const path = (arr) =>
    arr.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");

  // y-axis ticks
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const v = min + f * range;
    return { v, y: y(v) };
  });
  const fmtUsd = (v) =>
    "$" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });

  const firstDate = strategy[0]?.date;
  const lastDate = strategy[n - 1]?.date;

  return (
    <svg className="bt-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} y1={t.y} x2={width - padR} y2={t.y} stroke="var(--border)" strokeWidth="1" />
          <text x={padL - 8} y={t.y + 3} textAnchor="end" fontSize="10" fill="var(--text-faint)">
            {fmtUsd(t.v)}
          </text>
        </g>
      ))}
      <text x={padL} y={height - 8} fontSize="10" fill="var(--text-faint)">{firstDate}</text>
      <text x={width - padR} y={height - 8} textAnchor="end" fontSize="10" fill="var(--text-faint)">{lastDate}</text>

      <path d={path(benchmark)} fill="none" stroke="var(--text-faint)" strokeWidth="1.5" strokeDasharray="4 3" />
      <path d={path(strategy)} fill="none" stroke="var(--accent)" strokeWidth="2" />

      <g transform={`translate(${padL + 8}, ${padT + 6})`} fontSize="11">
        <line x1="0" y1="0" x2="18" y2="0" stroke="var(--accent)" strokeWidth="2" />
        <text x="24" y="4" fill="var(--text-dim)">策略</text>
        <line x1="70" y1="0" x2="88" y2="0" stroke="var(--text-faint)" strokeWidth="1.5" strokeDasharray="4 3" />
        <text x="94" y="4" fill="var(--text-dim)">买入持有</text>
      </g>
    </svg>
  );
}
