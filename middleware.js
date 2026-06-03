import { NextResponse } from "next/server";

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };

const enc = new TextEncoder();

async function validSession(token, secret) {
  if (!token || !token.includes(".") || !secret) return false;
  const [payload, sig] = token.split(".", 2);
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  const b64 = btoa(String.fromCharCode(...new Uint8Array(mac)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return b64 === sig;
}

export async function middleware(req) {
  const { pathname } = req.nextUrl;

  // Session-auth mode (funnel)
  if (process.env.QUIZ_ENABLED === "1") {
    if (pathname.startsWith("/login") || pathname.startsWith("/api/trading/auth/login")) {
      return NextResponse.next();
    }
    const token = req.cookies.get("sb_session")?.value;
    if (await validSession(token, process.env.SESSION_SECRET || "")) {
      return NextResponse.next();
    }
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // Basic Auth mode (Vercel) — unchanged
  const user = process.env.BASIC_AUTH_USER;
  const pass = process.env.BASIC_AUTH_PASSWORD;
  if (!user || !pass) return NextResponse.next();
  const header = req.headers.get("authorization");
  if (header) {
    const [scheme, encoded] = header.split(" ");
    if (scheme === "Basic" && encoded) {
      const decoded = atob(encoded);
      const i = decoded.indexOf(":");
      if (decoded.slice(0, i) === user && decoded.slice(i + 1) === pass) {
        return NextResponse.next();
      }
    }
  }
  return new NextResponse("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="StockBoard", charset="UTF-8"' },
  });
}
