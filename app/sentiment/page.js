"use client";

import { useEffect, useState } from "react";
import Nav from "../../components/Nav";

function timeAgo(ts) {
  if (!ts) return "";
  const diff = Date.now() / 1000 - ts;
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}

export default function SentimentPage() {
  const [symbol, setSymbol] = useState("");
  const [query, setQuery] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function load(sym) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/news?symbol=${encodeURIComponent(sym || "")}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "请求失败");
      setData(json);
    } catch (e) {
      setError(e.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(""); }, []);

  function submit(e) {
    e.preventDefault();
    setQuery(symbol.trim().toUpperCase());
    load(symbol.trim().toUpperCase());
  }

  const sent = data?.sentiment;
  const buzz = sent?.sentiment;

  return (
    <div className="container">
      <header className="header">
        <div className="brand">
          <div className="brand-logo">S</div>
          <div>
            <h1>舆情 · News</h1>
            <p>{query ? `${query} 相关新闻` : "市场综合新闻"} · Finnhub</p>
          </div>
        </div>
        <div className="header-meta"><Nav /></div>
      </header>

      <form onSubmit={submit} className="search-wrap" style={{ maxWidth: 460 }}>
        <input className="search-input" placeholder="输入代码看个股舆情(如 AAPL)，留空看市场新闻"
          value={symbol} onChange={(e) => setSymbol(e.target.value)} />
      </form>

      {sent && (buzz?.bullishPercent != null || sent.companyNewsScore != null) && (
        <div className="bt-metrics" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
          <div className="bt-metric up"><span>看多占比</span><b>{buzz?.bullishPercent != null ? (buzz.bullishPercent * 100).toFixed(0) + "%" : "—"}</b></div>
          <div className="bt-metric down"><span>看空占比</span><b>{buzz?.bearishPercent != null ? (buzz.bearishPercent * 100).toFixed(0) + "%" : "—"}</b></div>
          <div className="bt-metric"><span>新闻热度</span><b>{sent.buzz?.buzz ?? "—"}</b></div>
        </div>
      )}

      {error && <div className="notice error">获取失败:{error}</div>}
      {loading ? (
        <div className="empty">加载中…</div>
      ) : data?.news?.length ? (
        <div className="newslist">
          {data.news.map((n) => (
            <a className="newsitem" key={n.id || n.url} href={n.url} target="_blank" rel="noreferrer">
              {n.image && <img src={n.image} alt="" className="newsimg" loading="lazy" />}
              <div className="newsbody">
                <div className="newshead">{n.headline}</div>
                {n.summary && <div className="newssum">{n.summary}</div>}
                <div className="newsmeta">{n.source} · {timeAgo(n.datetime)}</div>
              </div>
            </a>
          ))}
        </div>
      ) : (
        !error && <div className="empty">暂无新闻</div>
      )}
    </div>
  );
}
