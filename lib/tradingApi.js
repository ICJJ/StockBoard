// Client for the local trading backend (FastAPI on the Mac that talks to TWS).
// Base URL is configurable so the same frontend works locally or against a
// tunneled/remote backend. Token is optional (only set when the backend
// has TRADING_API_TOKEN enabled, i.e. when exposed to the internet).
const BASE =
  process.env.NEXT_PUBLIC_TRADING_API || "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_TRADING_TOKEN || "";

function headers() {
  const h = { "Content-Type": "application/json" };
  if (TOKEN) h["Authorization"] = `Bearer ${TOKEN}`;
  return h;
}

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, { ...opts, headers: headers() });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || json.error || `HTTP ${res.status}`);
  return json;
}

export const tradingApi = {
  base: BASE,
  health: () => req("/health"),
  strategies: () => req("/strategies"),
  paperAccount: () => req("/paper/account"),
  paperPositions: () => req("/paper/positions"),
  backtest: (body) =>
    req("/backtest", { method: "POST", body: JSON.stringify(body) }),
};
