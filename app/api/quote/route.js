import { NextResponse } from "next/server";
import { finnhub } from "../../../lib/finnhub";

export const dynamic = "force-dynamic";

// GET /api/quote?symbols=AAPL,MSFT
// Returns an array of quotes enriched with the company name.
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const symbolsParam = searchParams.get("symbols") || searchParams.get("symbol") || "";
  const symbols = symbolsParam
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 30);

  if (symbols.length === 0) {
    return NextResponse.json({ error: "No symbols provided" }, { status: 400 });
  }

  try {
    const results = await Promise.all(
      symbols.map(async (symbol) => {
        try {
          const [quote, profile] = await Promise.all([
            finnhub("/quote", { symbol }),
            finnhub("/stock/profile2", { symbol }).catch(() => ({})),
          ]);
          return {
            symbol,
            name: profile?.name || symbol,
            logo: profile?.logo || null,
            currency: profile?.currency || "USD",
            current: quote.c ?? null,
            change: quote.d ?? null,
            percent: quote.dp ?? null,
            high: quote.h ?? null,
            low: quote.l ?? null,
            open: quote.o ?? null,
            prevClose: quote.pc ?? null,
            time: quote.t ?? null,
          };
        } catch (e) {
          return { symbol, error: e.message };
        }
      })
    );
    return NextResponse.json({ data: results, ts: Date.now() });
  } catch (e) {
    const status = e.status || 500;
    return NextResponse.json({ error: e.message }, { status });
  }
}
