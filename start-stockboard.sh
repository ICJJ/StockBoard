#!/usr/bin/env bash
# Start StockBoard locally with the IBKR trading backend, optionally exposed
# publicly via Tailscale Funnel (HTTPS + your tailnet domain).
#
# Prereqs: TWS paper account logged in with API enabled (port 7497).
#
# Usage:
#   ./start-stockboard.sh           # local only  -> http://localhost:3000
#   ./start-stockboard.sh --funnel  # also expose -> https://<machine>.<tailnet>.ts.net
set -euo pipefail
cd "$(dirname "$0")"

# Load local secrets (gitignored): BASIC_AUTH_USER / BASIC_AUTH_PASSWORD
[[ -f .env.trading ]] && set -a && . ./.env.trading && set +a

TS="${TAILSCALE:-/Applications/Tailscale.app/Contents/MacOS/Tailscale}"

# Site login (Basic Auth) — protects the public Funnel URL.
# Set these in your shell before running (do NOT hardcode here):
#   export BASIC_AUTH_USER=icjj BASIC_AUTH_PASSWORD='your-password'
if [[ "${1:-}" == "--funnel" && ( -z "${BASIC_AUTH_USER:-}" || -z "${BASIC_AUTH_PASSWORD:-}" ) ]]; then
  echo "✋ Refusing to expose publicly without auth."
  echo "   export BASIC_AUTH_USER=... BASIC_AUTH_PASSWORD=... first."
  exit 1
fi

# Backend stays bound to localhost only (never exposed directly).
echo "▶ starting trading backend on 127.0.0.1:8000 ..."
PYTHONPATH="$PWD" ./.venv-trading/bin/uvicorn trading.app:app \
  --host 127.0.0.1 --port 8000 --log-level warning &
BACK_PID=$!

echo "▶ building + starting Next app on :3000 ..."
npm run build >/dev/null 2>&1
npm start -- --port 3000 &
FRONT_PID=$!

cleanup() { kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if [[ "${1:-}" == "--funnel" ]]; then
  echo "▶ enabling Tailscale Funnel -> :3000 ..."
  "$TS" funnel --bg 3000
  echo "✅ Public URL: https://$("$TS" status --json | python3 -c 'import sys,json;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
  echo "   (protected by Basic Auth: user=$BASIC_AUTH_USER)"
else
  echo "✅ Local: http://localhost:3000"
fi

echo "Press Ctrl-C to stop."
wait
