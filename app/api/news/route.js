import { NextResponse } from "next/server";
import { finnhub } from "../../../lib/finnhub";

export const dynamic = "force-dynamic";

function ymd(d) {
  return d.toISOString().slice(0, 10);
}

// GET /api/news?symbol=AAPL  -> recent company news + (best-effort) sentiment
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const symbol = (searchParams.get("symbol") || "").trim().toUpperCase();

  try {
    if (!symbol) {
      // Market-wide general news
      const general = await finnhub("/news", { category: "general" });
      return NextResponse.json({
        symbol: null,
        news: (general || []).slice(0, 30).map(mapItem),
      });
    }

    const to = new Date();
    const from = new Date(to.getTime() - 7 * 86400_000);
    const news = await finnhub("/company-news", {
      symbol,
      from: ymd(from),
      to: ymd(to),
    });

    // Sentiment is premium on some plans — never fail the request over it.
    let sentiment = null;
    try {
      sentiment = await finnhub("/news-sentiment", { symbol });
    } catch {
      sentiment = null;
    }

    return NextResponse.json({
      symbol,
      sentiment,
      news: (news || []).slice(0, 40).map(mapItem),
    });
  } catch (e) {
    return NextResponse.json({ error: e.message }, { status: e.status || 500 });
  }
}

function mapItem(n) {
  return {
    id: n.id,
    headline: n.headline,
    summary: n.summary,
    source: n.source,
    url: n.url,
    image: n.image || null,
    datetime: n.datetime,
  };
}
