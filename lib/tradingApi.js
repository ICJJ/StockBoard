// Client for the trading backend. Calls go same-origin to the Next proxy
// (/api/trading/*), which forwards to the local FastAPI backend server-side
// and injects the auth token there. So the browser never holds the token and
// everything works through a single (optionally Tailscale-funneled) origin.
const BASE = process.env.NEXT_PUBLIC_TRADING_API || "/api/trading";

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json" },
  });
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
  live: () => req("/live"),
  backtest: (body) =>
    req("/backtest", { method: "POST", body: JSON.stringify(body) }),
};
