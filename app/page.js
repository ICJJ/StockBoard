"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";
import SearchBar from "../components/SearchBar";
import StockCard from "../components/StockCard";
import { quizApi } from "../lib/quizApi";

const DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META"];
const STORAGE_KEY = "stockboard.watchlist.v1";
const REFRESH_MS = 15000;
const MAX_HISTORY = 60;

// Is the US equities regular session open right now? (NYSE 9:30–16:00 ET, Mon–Fri.)
function getMarketStatus() {
  const now = new Date();
  const et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
  const day = et.getDay();
  const minutes = et.getHours() * 60 + et.getMinutes();
  const open = day >= 1 && day <= 5 && minutes >= 570 && minutes < 960;
  return { open, et };
}

export default function Page() {
  const [watchlist, setWatchlist] = useState(DEFAULT_WATCHLIST);
  const [quotes, setQuotes] = useState({});
  const [history, setHistory] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [market, setMarket] = useState({ open: false });
  const [hydrated, setHydrated] = useState(false);
  const [gate, setGate] = useState("checking");
  const watchRef = useRef(watchlist);

  // Load persisted watchlist on mount.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (Array.isArray(saved) && saved.length) setWatchlist(saved);
    } catch {}
    setHydrated(true);
  }, []);

  // Persist watchlist on change.
  useEffect(() => {
    watchRef.current = watchlist;
    if (hydrated) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(watchlist));
      } catch {}
    }
  }, [watchlist, hydrated]);

  // Market status clock.
  useEffect(() => {
    const tick = () => setMarket(getMarketStatus());
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  const fetchQuotes = useCallback(async () => {
    const symbols = watchRef.current;
    if (!symbols.length) {
      setQuotes({});
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`/api/quote?symbols=${symbols.join(",")}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "请求失败");

      const map = {};
      json.data.forEach((q) => (map[q.symbol] = q));
      setQuotes(map);
      setError(null);
      setUpdatedAt(Date.now());

      setHistory((prev) => {
        const next = { ...prev };
        json.data.forEach((q) => {
          if (q.current && !q.error) {
            const arr = (next[q.symbol] || []).concat(q.current);
            next[q.symbol] = arr.slice(-MAX_HISTORY);
          }
        });
        return next;
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Polling loop — restarts whenever the watchlist changes.
  useEffect(() => {
    if (!hydrated) return;
    setLoading(true);
    fetchQuotes();
    const id = setInterval(fetchQuotes, REFRESH_MS);
    return () => clearInterval(id);
  }, [watchlist, hydrated, fetchQuotes]);

  useEffect(() => {
    quizApi.state()
      .then((s) => { if (s.entered_today) setGate("ok"); else { setGate("redirect"); window.location.href = "/quiz"; } })
      .catch(() => setGate("ok"));
  }, []);

  // Leaderboard (left sidebar)
  const [board, setBoard] = useState([]);
  useEffect(() => {
    quizApi.leaderboard().then((d) => setBoard(d.leaderboard || [])).catch(() => {});
  }, []);

  function addSymbol(symbol) {
    const s = symbol.trim().toUpperCase();
    if (!s || watchlist.includes(s)) return;
    setWatchlist((w) => [...w, s]);
  }

  function removeSymbol(symbol) {
    setWatchlist((w) => w.filter((s) => s !== symbol));
    setHistory((h) => {
      const n = { ...h };
      delete n[symbol];
      return n;
    });
  }

  const updatedLabel = updatedAt
    ? new Date(updatedAt).toLocaleTimeString("en-US", { hour12: false })
    : "—";

  if (gate !== "ok") {
    return <div className="container"><p style={{ padding: 48, textAlign: "center", color: "var(--text-dim)" }}>每日一题校验中…</p></div>;
  }

  return (
    <div className="container">
      <header className="header">
        <div className="brand">
          <div className="brand-logo">S</div>
          <div>
            <h1>StockBoard</h1>
            <p>美股实时自选股看板 · Finnhub</p>
          </div>
        </div>
        <div className="header-meta">
          <Nav />
          <span className="market-status">
            <span className={`dot ${market.open ? "open" : "closed"}`} />
            {market.open ? "美股交易中" : "美股休市"}
          </span>
          <div className="refresh-row">
            <span>更新 {updatedLabel}</span>
            <button className="refresh-btn" onClick={fetchQuotes}>
              刷新
            </button>
          </div>
        </div>
      </header>

      <div className="board-layout">
        <aside className="board-side">
          <h2 className="side-title">排行榜</h2>
          {board.length === 0 ? (
            <p className="side-empty">暂无数据</p>
          ) : (
            <ol className="lb-list">
              {board.slice(0, 10).map((u, i) => (
                <li key={u.username} className="lb-row">
                  <span className="lb-rank">{i + 1}</span>
                  <span className="lb-name">{u.username}</span>
                  {u.streak > 0 && <span className="lb-streak">🔥{u.streak}</span>}
                  <span className="lb-pts">{u.points}<small>分</small></span>
                </li>
              ))}
            </ol>
          )}
          <a className="side-link" href="/leaderboard">完整排行榜 →</a>
        </aside>

        <div className="board-main">
          <SearchBar onAdd={addSymbol} existing={watchlist} />

          {error && (
            <div className="notice error">
              数据获取失败：{error}
              <br />
              请确认已在 Vercel 配置 FINNHUB_API_KEY 环境变量。
            </div>
          )}

          {loading && Object.keys(quotes).length === 0 ? (
            <div className="grid">
              {watchlist.map((s) => (
                <div key={s} className="skeleton" />
              ))}
            </div>
          ) : watchlist.length === 0 ? (
            <div className="empty">自选股为空，使用上方搜索框添加股票。</div>
          ) : (
            <div className="grid">
              {watchlist.map((s) => (
                <StockCard
                  key={s}
                  quote={quotes[s] || { symbol: s, name: "", current: null }}
                  history={history[s] || []}
                  onRemove={removeSymbol}
                />
              ))}
            </div>
          )}

          <footer className="footer">
            数据由 <a href="https://finnhub.io" target="_blank" rel="noreferrer">Finnhub</a> 提供 ·
            自动每 15 秒刷新 · 仅供参考，非投资建议
          </footer>
        </div>
      </div>
    </div>
  );
}
