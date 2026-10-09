#!/usr/bin/env bash
# Start the OpenCode free-tier proxy for pi (idempotent).
#
# Requires the OpenCode server to already be listening on :4096.
# Verify with:  curl -s http://127.0.0.1:4096/global/health
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${OC_PROXY_PORT:-4097}"
LOG="${OC_PROXY_LOG:-$DIR/proxy.log}"

if curl -sf -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "oc-proxy already running on :$PORT"
  exit 0
fi

if ! curl -sf -m 5 -H "Accept: application/json" http://127.0.0.1:4096/global/health >/dev/null 2>&1; then
  echo "error: no OpenCode server on :4096 (start it first)" >&2
  exit 1
fi

# Default: jail the OpenCode session root in a per-process temp dir outside every
# repository. Safe, but the models can then only use OpenCode's tools for compute,
# never to read project files.
#
# OC_PROXY_DIR=<repo> instead puts the session root at the project, which lets the
# free models reach the source through OpenCode's native tools. That is deliberate
# for some workloads and it means worktree isolation is NOT enforced for any worker
# on an opencode-free model - set it only when that is the intent.
OC_PROXY_DIR="${OC_PROXY_DIR:-}"
export OC_PROXY_DIR
cd "$DIR/../.." || exit 1
nohup node "$DIR/proxy.mjs" >"$LOG" 2>&1 &

for _ in $(seq 1 20); do
  sleep 0.5
  if curl -sf -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "oc-proxy listening on :$PORT (log: $LOG)"
    exit 0
  fi
done

echo "error: proxy did not come up; see $LOG" >&2
tail -5 "$LOG" >&2 || true
exit 1