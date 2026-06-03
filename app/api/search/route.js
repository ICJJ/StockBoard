import { NextResponse } from "next/server";
import { finnhub } from "../../../lib/finnhub";

export const dynamic = "force-dynamic";

// GET /api/search?q=apple
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const q = (searchParams.get("q") || "").trim();
  if (!q) return NextResponse.json({ data: [] });

  try {
    const res = await finnhub("/search", { q });
    const data = (res.result || [])
      // Keep common US-listed equities (skip exotic suffixes like .XX).
      .filter((r) => r.symbol && !r.symbol.includes("."))
      .slice(0, 12)
      .map((r) => ({
        symbol: r.symbol,
        description: r.description,
        type: r.type,
      }));
    return NextResponse.json({ data });
  } catch (e) {
    const status = e.status || 500;
    return NextResponse.json({ error: e.message }, { status });
  }
}
