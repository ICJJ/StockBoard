"use client";

import { useEffect, useRef, useState } from "react";

export default function SearchBar({ onAdd, existing = [] }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);
  const timer = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const term = q.trim();
    if (!term) {
      setResults([]);
      return;
    }
    setLoading(true);
    timer.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(term)}`);
        const json = await res.json();
        setResults(json.data || []);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => timer.current && clearTimeout(timer.current);
  }, [q]);

  function pick(symbol) {
    onAdd(symbol);
    setQ("");
    setResults([]);
    setOpen(false);
  }

  function onSubmit(e) {
    e.preventDefault();
    const term = q.trim().toUpperCase();
    if (term) pick(term);
  }

  return (
    <div className="search-wrap" ref={boxRef}>
      <form onSubmit={onSubmit}>
        <input
          className="search-input"
          placeholder="搜索并添加股票（如 AAPL、Tesla）…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
        />
      </form>
      {open && (
        <div className="search-results">
          {loading && <div className="search-hint">搜索中…</div>}
          {!loading && results.length === 0 && (
            <div className="search-hint">无匹配结果，回车可直接按代码添加</div>
          )}
          {!loading &&
            results.map((r) => {
              const added = existing.includes(r.symbol);
              return (
                <div
                  key={r.symbol}
                  className="search-item"
                  onClick={() => !added && pick(r.symbol)}
                  style={added ? { opacity: 0.5, cursor: "default" } : undefined}
                >
                  <span className="sym">{r.symbol}</span>
                  <span className="desc">
                    {added ? "已添加" : r.description}
                  </span>
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
}
