#!/bin/sh
# Starts a throwaway OpenTrack on port 8099 (SQLite in a temp folder), seeds demo data,
# then clicks through every view with jsdom. Needs Python with backend/requirements-dev.txt and Node 18+.
set -e
cd "$(dirname "$0")"
DATA=$(mktemp -d)
# exec so $! is the server itself, not the subshell around it: without it the trap kills only
# the subshell, the server keeps port 8099, and the next run fails with "address already in use".
(cd ../../backend && OPENTRACK_DATA="$DATA" DATABASE_URL="sqlite:///$DATA/ui.db" exec python -m uvicorn app.main:app --port 8099 --log-level warning) &
PID=$!
trap 'kill $PID 2>/dev/null; rm -rf "$DATA"' EXIT
for i in $(seq 1 40); do curl -sf http://127.0.0.1:8099/api/health >/dev/null && break; sleep 0.5; done
python seed.py
[ -d node_modules ] || npm install --no-audit --no-fund --silent
node smoke.js
