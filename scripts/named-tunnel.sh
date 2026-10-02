#!/bin/sh
# Put Freehold on a fixed hostname with a named Cloudflare tunnel.
#
# A quick tunnel gets a random name that changes on every restart, which breaks bookmarks and every
# link already sent by email. A named tunnel keeps one hostname across restarts and reboots.
#
# Before running this, once:
#     cloudflared tunnel login        # opens a browser; pick the domain to use
#
# Then:
#     sh scripts/named-tunnel.sh tracker.yourdomain.com
#
set -e
HOST="$1"
NAME="${2:-freehold}"
PORT="${FREEHOLD_PORT:-8080}"
CF="$HOME/.cloudflared"

if [ -z "$HOST" ]; then
  echo "usage: sh scripts/named-tunnel.sh <hostname> [tunnel-name]" >&2
  exit 2
fi
if [ ! -f "$CF/cert.pem" ]; then
  echo "Not authorised yet. Run this first, and pick the domain you want to use:" >&2
  echo "    cloudflared tunnel login" >&2
  exit 2
fi

echo "==> tunnel '$NAME'"
if cloudflared tunnel list 2>/dev/null | awk '{print $2}' | grep -qx "$NAME"; then
  echo "    already exists, reusing it"
else
  cloudflared tunnel create "$NAME"
fi
ID=$(cloudflared tunnel list 2>/dev/null | awk -v n="$NAME" '$2==n {print $1}')
[ -n "$ID" ] || { echo "could not determine the tunnel id" >&2; exit 1; }
echo "    id $ID"

echo "==> DNS $HOST -> $NAME"
# Safe to re-run: it updates the record if it already points here.
cloudflared tunnel route dns "$NAME" "$HOST" 2>&1 | sed 's/^/    /' || true

echo "==> config"
cat > "$CF/config.yml" <<EOF
tunnel: $ID
credentials-file: $CF/$ID.json

ingress:
  - hostname: $HOST
    service: http://localhost:$PORT
  # Anything else that reaches this tunnel is refused rather than quietly served.
  - service: http_status:404
EOF
echo "    wrote $CF/config.yml"

echo "==> installing as a service, so it survives a reboot"
if cloudflared service install 2>&1 | sed 's/^/    /'; then :; else
  echo "    service install needs sudo; run it yourself with:"
  echo "        sudo cloudflared service install"
  echo "    or keep it in the foreground with: cloudflared tunnel run $NAME"
fi

echo "==> pointing Freehold at https://$HOST"
if [ -f .env ]; then
  if grep -q '^BASE_URL=' .env; then
    sed -i '' "s|^BASE_URL=.*|BASE_URL=https://$HOST|" .env
  else
    echo "BASE_URL=https://$HOST" >> .env
  fi
  echo "    BASE_URL=https://$HOST"
  docker compose up -d --force-recreate >/dev/null 2>&1 && echo "    recreated the app so it takes effect"
fi

echo
echo "Done. Check it:"
echo "    curl -s https://$HOST/api/health"
echo "    python scripts/preflight.py https://$HOST --compose opentrack"
