import { NextResponse } from "next/server";

// Protect the whole site (pages + API) with HTTP Basic Auth.
// Credentials come from env vars BASIC_AUTH_USER / BASIC_AUTH_PASSWORD.
// If either is unset, the site is left open (no auth) — so the app still
// works locally without configuring credentials.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

export function middleware(req) {
  const user = process.env.BASIC_AUTH_USER;
  const pass = process.env.BASIC_AUTH_PASSWORD;
  if (!user || !pass) return NextResponse.next();

  const header = req.headers.get("authorization");
  if (header) {
    const [scheme, encoded] = header.split(" ");
    if (scheme === "Basic" && encoded) {
      const decoded = atob(encoded);
      const sep = decoded.indexOf(":");
      const u = decoded.slice(0, sep);
      const p = decoded.slice(sep + 1);
      if (u === user && p === pass) return NextResponse.next();
    }
  }

  return new NextResponse("Authentication required.", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="StockBoard", charset="UTF-8"',
    },
  });
}
