#!/bin/bash
set -e
cd "$(dirname "$0")"

pip install -r requirements.txt -q
mkdir -p tmp

# Read configured port from config.ini, default 8765
BASE_PORT=$(python3 -c "
import configparser, pathlib
c = configparser.ConfigParser()
c.read(pathlib.Path('.') / 'config.ini', encoding='utf-8')
print(c.get('app', 'port', fallback='8765'))
" 2>/dev/null || echo "8765")

# ── Find an available port ────────────────────────────────────────────────────
find_port() {
  local port=$1
  while lsof -ti :"$port" > /dev/null 2>&1; do
    echo "Port $port is in use, trying $((port + 1))…"
    port=$((port + 1))
  done
  echo "$port"
}

PORT=$(find_port "$BASE_PORT")

if [ "$PORT" != "$BASE_PORT" ]; then
  echo "⚠️  Port $BASE_PORT was occupied — using port $PORT instead"
fi

URL="http://localhost:${PORT}"

# ── Write the resolved port so main.py picks it up ───────────────────────────
export TERMINALHUB_PORT="$PORT"

# ── Start server ──────────────────────────────────────────────────────────────
echo "🚀 Starting TerminalHub → $URL"
python3 main.py &
SERVER_PID=$!

# ── Wait until server is ready (up to 15 s) ──────────────────────────────────
echo "⏳ Waiting for server to be ready…"
READY=0
for i in $(seq 1 50); do
  if curl -sf "$URL" > /dev/null 2>&1; then
    READY=1
    break
  fi
  # If server process died early, bail out immediately
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "❌ Server process exited unexpectedly. Check the logs."
    exit 1
  fi
  sleep 0.3
done

if [ "$READY" -eq 1 ]; then
  echo "✅ Server ready. Opening browser…"
  open "$URL"
else
  echo "⚠️  Server did not respond after 15 s — it may still be starting."
fi

# Keep script alive and forward Ctrl-C cleanly
trap "echo ''; echo '🛑 Stopping TerminalHub…'; kill $SERVER_PID 2>/dev/null" INT TERM
wait $SERVER_PID
