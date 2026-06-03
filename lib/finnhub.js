// Server-side Finnhub client. The API key is read from the environment and
// never exposed to the browser — all calls are proxied through /api routes.

const BASE = "https://finnhub.io/api/v1";

export function getApiKey() {
  const key = process.env.FINNHUB_API_KEY;
  if (!key) {
    throw new Error("FINNHUB_API_KEY is not set");
  }
  return key;
}

export async function finnhub(path, params = {}) {
  const key = getApiKey();
  const url = new URL(BASE + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  });
  url.searchParams.set("token", key);

  const res = await fetch(url.toString(), {
    // Always fetch fresh data for quotes.
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    const err = new Error(`Finnhub ${path} failed: ${res.status} ${text}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
