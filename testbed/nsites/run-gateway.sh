#!/usr/bin/env bash
# Run the pinned upstream nsite-gateway (Deno) against the local fake relay
# and fake blossom, in front of which Caddy serves https.
#
# Prereqs: deno (>=2.7.7) on PATH or $DENO_BIN, the upstream source cloned at
# the pinned commit under upstream/nsite-gateway, fake-relay.py and
# fake-blossom.py running.
#
# Usage: ./run-gateway.sh [--port 3000]
set -euo pipefail

DENO_BIN="${DENO_BIN:-deno}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="${GATEWAY_DIR:-$HERE/upstream/nsite-gateway}"
PORT=3000
if [[ "${1:-}" == "--port" ]]; then PORT="$2"; fi

export NSITE_PORT="$PORT"
export PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-sites.nostrhost.test}"
export LOOKUP_RELAYS="${LOOKUP_RELAYS:-ws://127.0.0.1:7777}"
export NOSTR_RELAYS="${NOSTR_RELAYS:-ws://127.0.0.1:7777}"
export BLOSSOM_SERVERS="${BLOSSOM_SERVERS:-http://127.0.0.1:8787}"
export BLOSSOM_PROXY="${BLOSSOM_PROXY:-}"
export MAX_FILE_SIZE="${MAX_FILE_SIZE:-2 MB}"
export CACHE_TIME="${CACHE_TIME:-3600}"
export CACHE_PATH="${CACHE_PATH:-$HERE/.cache/nsite-gateway.kv}"

cd "$GATEWAY_DIR"
exec "$DENO_BIN" run --frozen --cached-only --unstable-kv \
  --allow-env --allow-net --allow-read --allow-write main.ts