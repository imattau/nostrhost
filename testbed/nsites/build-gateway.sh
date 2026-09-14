#!/usr/bin/env bash
# Clone the pinned upstream nsite-gateway and cache its Deno dependencies.
# Reproducible without Docker: runs the gateway with `deno run` (run-gateway.sh).
set -euo pipefail

PIN="${NSITE_GATEWAY_PIN:-558326ae5bbaf209e63d5a3e53b6bbad508b336a}"
DENO_BIN="${DENO_BIN:-deno}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$HERE/upstream/nsite-gateway"

mkdir -p "$HERE/upstream"
if [ ! -d "$DIR/.git" ]; then
  git clone https://github.com/hzrd149/nsite-gateway.git "$DIR"
fi
git -C "$DIR" fetch --quiet origin "$PIN" 2>/dev/null || true
git -C "$DIR" checkout --quiet "$PIN"
echo "gateway at $(git -C "$DIR" rev-parse HEAD)"
(cd "$DIR" && "$DENO_BIN" cache --unstable-kv main.ts)
echo "dependencies cached"