import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Server-side proxy to the local trading backend (FastAPI on the Mac).
// Keeps the backend single-origin behind the Next app: the browser only ever
// talks to this app, and the backend token (if any) stays server-side.
const BACKEND = process.env.TRADING_BACKEND_URL || "http://localhost:8000";
const TOKEN = process.env.TRADING_API_TOKEN || "";

async function forward(request, params, method) {
  const path = (params.path || []).join("/");
  const url = new URL(request.url);
  const target = `${BACKEND}/${path}${url.search}`;

  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers["Authorization"] = `Bearer ${TOKEN}`;
  const cookie = request.headers.get("cookie");
  if (cookie) headers["cookie"] = cookie;

  const init = { method, headers };
  if (method === "POST") init.body = await request.text();

  try {
    const res = await fetch(target, init);
    const text = await res.text();
    const response = new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
    const setCookie = res.headers.get("set-cookie");
    if (setCookie) response.headers.set("set-cookie", setCookie);
    return response;
  } catch (e) {
    return NextResponse.json(
      { detail: `交易后端不可达（${BACKEND}）：${e.message}` },
      { status: 503 }
    );
  }
}

export async function GET(request, { params }) {
  return forward(request, params, "GET");
}

export async function POST(request, { params }) {
  return forward(request, params, "POST");
}
