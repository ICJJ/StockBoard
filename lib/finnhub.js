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

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function finnhub(path, params = {}, retries = 2) {
  const key = getApiKey();
  const url = new URL(BASE + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  });
  url.searchParams.set("token", key);

  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url.toString(), {
        cache: "no-store", // always fresh quotes
        headers: { Accept: "application/json" },
      });
      if (res.status === 429 || res.status >= 500) {
        // transient (rate limit / upstream) — retry
        const text = await res.text().catch(() => "");
        const err = new Error(`Finnhub ${path} ${res.status} ${text}`);
        err.status = res.status;
        throw err;
      }
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        const err = new Error(`Finnhub ${path} failed: ${res.status} ${text}`);
        err.status = res.status; // 4xx — don't retry
        throw err;
      }
      return res.json();
    } catch (e) {
      lastErr = e;
      // Retry on network-level errors ("fetch failed") and 429/5xx; give up on other 4xx.
      const retriable = e.status === 429 || (e.status >= 500) || e.status === undefined;
      if (!retriable || attempt === retries) break;
      await sleep(250 * (attempt + 1)); // 250ms, 500ms backoff
    }
  }
  throw lastErr;
}
